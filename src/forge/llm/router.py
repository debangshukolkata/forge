"""Routes each role to its configured model, with redaction, retries, fallback and cost (spec §5.2, §5.3)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from forge.config import ROLES, ForgeConfig, Secrets, model_secret_names
from forge.errors import ConfigError, LLMError, LLMRateLimitError
from forge.llm.azure_openai import AzureOpenAIProvider
from forge.llm.base import ChatRequest, LLMProvider, LLMResponse, TextDeltaCallback
from forge.llm.cost import CostTracker
from forge.llm.retry import MAX_HONOURED_RETRY_AFTER_S, Sleeper, with_retries
from forge.llm.tokens import count_request_tokens
from forge.safety.redact import Redactor, default_redactor

ProviderFactory = Callable[[str], LLMProvider]
NoticeCallback = Callable[[str, dict[str, Any]], Awaitable[None]]


class LLMRouter:
    def __init__(
        self,
        config: ForgeConfig,
        secrets: Secrets,
        *,
        provider_factory: ProviderFactory | None = None,
        redactor: Redactor = default_redactor,
        sleep: Sleeper = asyncio.sleep,
        on_notice: NoticeCallback | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self._secrets = secrets
        self._provider_factory = provider_factory or self._create_provider
        self._providers: dict[str, LLMProvider] = {}
        self._redactor = redactor
        self._sleep = sleep
        self._on_notice = on_notice
        self._clock = clock
        self._resting_until: dict[str, float] = {}  # model key -> clock time its rest ends (D-465)
        self.role_models: dict[str, str | None] = {role: getattr(config.llm.roles, role) for role in ROLES}
        self.cost = CostTracker(config.llm.models, config.limits.session_budget_usd)

    # --- role/model selection (config defaults, changed per session with /model) ---

    def model_for_role(self, role: str) -> str:
        if role not in self.role_models:
            raise ConfigError(f"Unknown role '{role}'. Roles: {', '.join(ROLES)}")
        model_key = self.role_models[role]
        if model_key is None and role in ("critic", "planner"):
            # no separate critic or planner chosen: the builder's own model (D-409, D-411)
            model_key = self.role_models["coder"]
        if model_key is None:
            raise ConfigError(f"No model is configured for role '{role}'")
        return model_key

    def set_role_model(self, role: str, model_key: str) -> None:
        if role not in self.role_models:
            raise ConfigError(f"Unknown role '{role}'. Roles: {', '.join(ROLES)}")
        if model_key not in self.config.llm.models:
            raise ConfigError(
                f"Unknown model '{model_key}'. Models: {', '.join(sorted(self.config.llm.models))}"
            )
        self.role_models[role] = model_key

    def _configured(self, model_key: str) -> bool:
        """A fallback whose .env values were never added is not available; the original error stands."""
        if self._provider_factory != self._create_provider:
            return True  # a test supplied its own providers
        names = model_secret_names(self.config, self.config.llm.models[model_key])
        return all(self._secrets.get(name) for name in names)

    def provider(self, model_key: str) -> LLMProvider:
        if model_key not in self._providers:
            self._providers[model_key] = self._provider_factory(model_key)
        return self._providers[model_key]

    def _create_provider(self, model_key: str) -> LLMProvider:
        model = self.config.llm.models[model_key]
        if model.provider == "gemini":
            try:
                from forge.llm.gemini import GeminiProvider  # optional dependency, imported only when used
            except ImportError as error:
                raise ConfigError(
                    f"Model '{model_key}' uses Gemini, which needs the google-genai package: pip install google-genai"
                ) from error
            return GeminiProvider(model_key, model, self.config.llm.providers.gemini, self._secrets)
        return AzureOpenAIProvider(model_key, model, self.config.llm.providers.azure, self._secrets)

    def _resting(self, model_key: str) -> bool:
        return self._clock() < self._resting_until.get(model_key, 0.0)

    def _rest(self, model_key: str, error: LLMError) -> float:
        """Lets a rate-limited or failing model rest: calls go elsewhere until the time is up (D-465)."""
        seconds = self.config.llm.rotation_cooldown_s
        if isinstance(error, LLMRateLimitError) and error.retry_after_s:
            seconds = max(seconds, min(error.retry_after_s, MAX_HONOURED_RETRY_AFTER_S))
        self._resting_until[model_key] = self._clock() + seconds
        return seconds

    def _fits(self, model_key: str, request: ChatRequest | None) -> bool:
        """A smaller context window (gpt-4o has 128k) must not be handed a conversation it cannot hold."""
        if request is None:
            return True
        needed = count_request_tokens(request.messages, request.tools) * 1.1 + (
            request.max_output_tokens or 0
        )
        return needed < self.config.llm.models[model_key].context_window

    def _usable(self, key: str | None, failing_key: str, request: ChatRequest | None) -> bool:
        return bool(
            key
            and key != failing_key
            and self._configured(key)
            and not self._resting(key)
            and self._fits(key, request)
        )

    def _fallback_for(self, failing_key: str, request: ChatRequest | None = None) -> str | None:
        """The model to switch to when `failing_key` is rate limited or down (D-411, D-465).
        A model in config `llm.rotation` goes to the next usable one in that order (preference order, so the strongest
        comes first). Otherwise: the fallback role, then the coder's model, then `fallback_also`, preferring another
        provider because a rate limit or an outage usually hits one provider and not the other."""
        rotation = self.config.llm.rotation
        if failing_key in rotation:
            for key in rotation:
                if self._usable(key, failing_key, request):
                    return key
        failing = self.config.llm.models[failing_key]
        candidates: list[str] = []
        for named in (
            self.role_models.get("fallback"),
            self.role_models.get("coder"),
            *self.config.llm.fallback_also,
        ):
            if named and named not in candidates and self._usable(named, failing_key, request):
                candidates.append(named)
        other_family = [key for key in candidates if self.config.llm.models[key].provider != failing.provider]
        chosen = other_family or candidates
        return chosen[0] if chosen else None

    # --- calls ---

    async def chat(
        self, role: str, request: ChatRequest, on_text_delta: TextDeltaCallback | None = None
    ) -> LLMResponse:
        self.cost.check_budget()
        model_key = self.model_for_role(role)
        if self._resting(model_key):  # rate limited a moment ago: use the next model until its rest is over
            model_key = self._fallback_for(model_key, request) or model_key
        has_alternative = self._fallback_for(model_key, request) is not None
        try:
            # With somewhere else to go, wait once and switch instead of going through every retry.
            response = await self._call_with_retries(
                role, model_key, request, on_text_delta, quick=has_alternative
            )
        except LLMError as error:
            fallback = self._fallback_for(model_key, request) if error.retryable else None
            if fallback is None:
                raise
            seconds = self._rest(model_key, error)
            why = "is rate limited" if isinstance(error, LLMRateLimitError) else "failed"
            await self._notice(
                "fallback",
                {
                    "role": role,
                    "from_model": model_key,
                    "to_model": fallback,
                    "rest_s": round(seconds),
                    "reason": str(error)[:300],
                    "text": f"{model_key} {why} ({str(error)[:160]}); using {fallback} for the next "
                    f"{max(1, round(seconds / 60))} min, then back",
                },
            )
            model_key = fallback
            response = await self._call_with_retries(role, model_key, request, on_text_delta)
        cost = self.cost.record(model_key, role, response.usage)
        await self._notice(
            "usage",
            {
                "role": role,
                "model": model_key,
                "served_model": response.served_model,
                "usage": response.usage.model_dump(),
                "cost_usd": cost,
                "total_usd": self.cost.total_usd,
                "summary": self.cost.summary(),
            },
        )
        return response

    async def _call_with_retries(
        self,
        role: str,
        model_key: str,
        request: ChatRequest,
        on_text_delta: TextDeltaCallback | None,
        quick: bool = False,
    ) -> LLMResponse:
        prepared = self.prepare_request(role, model_key, request)
        provider = self.provider(model_key)

        async def on_retry(attempt: int, error: LLMError, delay_s: float) -> None:
            await self._notice(
                "retry",
                {
                    "model": model_key,
                    "attempt": attempt,
                    "delay_s": round(delay_s, 2),
                    "reason": str(error)[:300],
                    # The web chat shows `text`; without it the user sees only the word "retry" (D-246).
                    "text": f"Model call to {model_key} failed ({str(error)[:200]}); retrying in "
                    f"{round(delay_s)}s (attempt {attempt})",
                },
            )

        retry = self.config.llm.retry
        if quick:
            retry = retry.model_copy(update={"max_attempts": min(retry.max_attempts, 2)})
        return await with_retries(
            lambda: provider.chat(prepared, on_text_delta), retry, self._sleep, on_retry
        )

    def prepare_request(self, role: str, model_key: str, request: ChatRequest) -> ChatRequest:
        """Redacts secrets from everything sent and fills in the model's defaults."""
        model = self.config.llm.models[model_key]
        messages = [
            message.model_copy(
                update={
                    "content": self._redactor.redact(message.content),
                    "tool_calls": [
                        call.model_copy(update={"raw_arguments": self._redactor.redact(call.raw_arguments)})
                        for call in message.tool_calls
                    ],
                }
            )
            for message in request.messages
        ]
        effort = request.reasoning_effort
        if effort is None and model.reasoning_effort is not None:
            effort = self.config.llm.role_reasoning_effort.get(role, model.reasoning_effort)
        return request.model_copy(
            update={
                "messages": messages,
                "reasoning_effort": effort if model.reasoning_effort is not None else None,
                "max_output_tokens": min(request.max_output_tokens or model.max_output, model.max_output),
            }
        )

    async def _notice(self, kind: str, data: dict[str, Any]) -> None:
        if self._on_notice is not None:
            await self._on_notice(kind, data)
