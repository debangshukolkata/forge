"""Per-call cost accounting and the session budget cap (spec §5.3)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from forge.config import CostConfig, ModelConfig
from forge.errors import BudgetExceededError
from forge.llm.base import Usage
from forge.llm.usage_ledger import UsageLedger

TOKENS_PER_PRICE_UNIT = 1_000_000


class CostTracker:
    def __init__(self, models: dict[str, ModelConfig], budget_usd: float) -> None:
        self._models = models
        self.budget_usd = budget_usd
        self.total_usd = 0.0
        self.calls = 0
        self.usage_by_model: dict[str, Usage] = defaultdict(Usage)
        self.cost_by_role: dict[str, float] = defaultdict(float)
        # Set by the session when a project is open: per-phase/per-task tokens and cost (D-118).
        self.ledger: UsageLedger | None = None
        self.where: Callable[[], tuple[str, str | None]] | None = None

    def cost_of(self, model_key: str, usage: Usage) -> float:
        price = self._models[model_key].price_per_mtok
        cached = min(usage.cached_input_tokens, usage.input_tokens)
        uncached = usage.input_tokens - cached
        dollars = uncached * price.input + cached * price.cached_input + usage.output_tokens * price.output
        return dollars / TOKENS_PER_PRICE_UNIT

    def record(self, model_key: str, role: str, usage: Usage) -> float:
        cost = self.cost_of(model_key, usage)
        self.total_usd += cost
        self.calls += 1
        self.usage_by_model[model_key] = self.usage_by_model[model_key] + usage
        self.cost_by_role[role] += cost
        if self.ledger is not None:
            phase, task = self.where() if self.where is not None else ("direct", None)
            self.ledger.add(phase, task, usage, cost)
        return cost

    def check_budget(self) -> None:
        if self.total_usd >= self.budget_usd:
            raise BudgetExceededError(
                f"Session budget of ${self.budget_usd:.2f} reached (spent ${self.total_usd:.2f}). "
                "Approve a higher budget to continue."
            )

    def raise_budget(self, new_budget_usd: float) -> None:
        """Called only after the user approves continuing."""
        self.budget_usd = new_budget_usd

    def summary(self) -> dict[str, object]:
        return {
            "total_usd": round(self.total_usd, 6),
            "budget_usd": self.budget_usd,
            "calls": self.calls,
            "cost_by_role": {role: round(cost, 6) for role, cost in self.cost_by_role.items()},
            "usage_by_model": {key: usage.model_dump() for key, usage in self.usage_by_model.items()},
            "project": self.ledger.summary() if self.ledger is not None else None,
        }


def format_money(usd: float, config: CostConfig) -> str:
    if config.display_currency == "INR":
        return f"₹{usd * config.inr_per_usd:,.2f}"
    return f"${usd:,.4f}"
