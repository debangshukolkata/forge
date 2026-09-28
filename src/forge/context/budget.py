"""Token budget (spec §10.1) and calibrated token estimates (DECISIONS D-052).

usable  = context_window - max_output - safety
fixed   = system prompt + tool schemas
pinned  = pinned blocks (capped at a share of usable)
history = usable - fixed - pinned

Estimates use tiktoken, scaled by how the last real request's estimate compared with the provider's
reported input tokens. That folds in what Forge can't count itself (encrypted reasoning items, per-message
framing) without guessing.
"""

from __future__ import annotations

from dataclasses import dataclass

from forge.config import ContextConfig, ModelConfig
from forge.llm.base import Message, ToolSpec
from forge.llm.tokens import count_message_tokens, count_request_tokens, count_tools_tokens

MIN_CALIBRATION = 0.8
MAX_CALIBRATION = 2.0


@dataclass
class Breakdown:
    usable: int
    fixed: int
    pinned: int
    history: int

    @property
    def used(self) -> int:
        return self.fixed + self.pinned + self.history

    @property
    def free(self) -> int:
        return max(0, self.usable - self.used)

    @property
    def percent(self) -> float:
        return round(100 * self.used / self.usable, 1) if self.usable else 100.0


class ContextBudget:
    def __init__(self, model: ModelConfig, config: ContextConfig) -> None:
        self.model = model
        self.config = config
        self.calibration = 1.0

    @property
    def usable(self) -> int:
        return int(
            self.model.context_window
            - self.model.max_output
            - self.config.safety_fraction * self.model.context_window
        )

    @property
    def pinned_cap(self) -> int:
        return int(self.usable * self.config.pinned_cap_fraction)

    def estimate(self, messages: list[Message], tools: list[ToolSpec]) -> int:
        return int(count_request_tokens(messages, tools) * self.calibration)

    def estimate_messages(self, messages: list[Message]) -> int:
        return int(sum(count_message_tokens(m) for m in messages) * self.calibration)

    def estimate_tools(self, tools: list[ToolSpec]) -> int:
        return int(count_tools_tokens(tools) * self.calibration)

    def calibrate(self, estimated_raw: int, reported_input_tokens: int) -> None:
        """Called after each model call with the raw tiktoken estimate and what the provider reported."""
        if estimated_raw > 0 and reported_input_tokens > 0:
            ratio = reported_input_tokens / estimated_raw
            self.calibration = min(MAX_CALIBRATION, max(MIN_CALIBRATION, ratio))

    def history_budget(self, fixed: int, pinned: int) -> int:
        return max(0, self.usable - fixed - pinned)
