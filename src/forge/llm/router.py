"""Routes each role to its configured model, with redaction, retries, fallback and cost (spec §5.2, §5.3)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from forge.config import ROLES, ForgeConfig, Secrets, model_secret_names
from forge.errors import (
    ConfigError,
    LLMContentFilterError,
    LLMContextLengthError,
    LLMError,
    LLMRateLimitError,
)
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
        self._back_unannounced: set[str] = set()  # models whose rest is over but the chat was not told yet
        self._switched: dict[
            str, str
        ] = {}  # preferred model -> the one used for the rest of this request (D-643)
        self._in_request = False
        self.answered_models: set[str] | None = (
            None  # models that answered the Environment test; None: not tested
        )
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
        self._back_unannounced.add(model_key)
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

    def _rotation(self) -> list[str]:
        """The configured rotation with Gemini put where the user wants it (D-643)."""
        llm = self.config.llm
        order = list(llm.rotation)
        gemini = llm.gemini_on_quota_model
        if llm.gemini_on_quota == "never" or not order or gemini in order or gemini not in llm.models:
            return order
        if self.answered_models is None or gemini not in self.answered_models:
            return order  # it never answered a test here
        at = 1
        if llm.gemini_on_quota == "last":
            at = next((i for i, key in enumerate(order) if key in llm.rotation_last_resort), len(order))
        return [*order[:at], gemini, *order[at:]]

    def _fallback_for(
        self, failing_key: str, request: ChatRequest | None = None, tried: tuple[str, ...] = ()
    ) -> str | None:
        """The model to switch to when `failing_key` is rate limited or down (D-411, D-465, D-643).
        A model in the rotation goes to the next usable one in that order (preference order, so the strongest comes
        first; the last-resort models after everything else). Otherwise: the fallback role, then the coder's model,
        then `fallback_also`, preferring another provider because a rate limit or an outage usually hits one provider
        and not the other."""
        rotation = self._rotation()
        weak = set(self.config.llm.rotation_last_resort)
        in_rotation = failing_key in rotation
        if in_rotation:
            for key in rotation:
                if key not in weak and key not in tried and self._usable(key, failing_key, request):
                    return key
        failing = self.config.llm.models[failing_key]
        candidates: list[str] = []
        for named in (
            self.role_models.get("fallback"),
            self.role_models.get("coder"),
            *self.config.llm.fallback_also,
        ):
            if in_rotation and named in weak:
                continue  # the last-resort models come below, in the order of the rotation
            if (
                named
                and named not in candidates
                and named not in tried
                and self._usable(named, failing_key, request)
            ):
                candidates.append(named)
        other_family = [key for key in candidates if self.config.llm.models[key].provider != failing.provider]
        chosen = other_family or candidates
        if chosen:
            return chosen[0]
        if in_rotation:
            for key in rotation:
                if key in weak and key not in tried and self._usable(key, failing_key, request):
                    return key
        return None

    def begin_request(self) -> None:
        """A new request of the user: the preferred models are tried first again (D-643)."""
        self._in_request = True
        self._switched.clear()

    def _start_model(self, preferred: str, request: ChatRequest) -> str:
        """The preferred model, or the one this request was moved to: a switch back in the middle of the work costs the
        cache, and the model that comes back has not seen its own reasoning since (D-643)."""
        moved = self._switched.get(preferred)
        if moved and not self._resting(moved) and self._fits(moved, request):
            return moved
        if self._resting(preferred):
            return self._fallback_for(preferred, request) or preferred
        return preferred

    # --- calls ---

    async def chat(
        self, role: str, request: ChatRequest, on_text_delta: TextDeltaCallback | None = None
    ) -> LLMResponse:
        self.cost.check_budget()
        preferred = self.model_for_role(role)
        model_key = self._start_model(preferred, request)
        if model_key == preferred and preferred in self._back_unannounced and not self._resting(preferred):
            self._back_unannounced.discard(preferred)  # said once, on the first call after the rest
            await self._notice(
                "switch_back",
                {"role": role, "model": preferred, "text": f"{preferred} has rested; using it again"},
            )
        tried: list[str] = []
        weak = self.config.llm.rotation_last_resort
        while True:
            alternative = self._fallback_for(model_key, request, (*tried, model_key))
            patience: float | None = None
            if alternative is not None:
                # With somewhere else to go: a short wait, then the next model. A coder waits longer before a weak one.
                weaker = alternative in weak and model_key not in weak and role == "coder"
                patience = (
                    self.config.llm.last_resort_patience_s if weaker else self.config.llm.rotation_patience_s
                )
            try:
                response = await self._call_with_retries(role, model_key, request, on_text_delta, patience)
                break
            except LLMError as error:
                # A replacement that refuses (no access, a request it does not take) is passed over too; what the
                # request itself is at fault for is not.
                moved_on = model_key != preferred and not isinstance(
                    error, LLMContextLengthError | LLMContentFilterError
                )
                if not error.retryable and not moved_on:
                    raise
                tried.append(model_key)
                fallback = self._fallback_for(model_key, request, tuple(tried))
                if fallback is None:
                    raise
                seconds = self._rest(model_key, error)
                why = "is rate limited" if isinstance(error, LLMRateLimitError) else "failed"
                if self._in_request and fallback not in weak:
                    self._switched[preferred] = fallback
                until = (
                    "until this request is finished"
                    if self._in_request and fallback not in weak
                    else f"for the next {max(1, round(seconds / 60))} min, then back"
                )
                await self._notice(
                    "fallback",
                    {
                        "role": role,
                        "from_model": model_key,
                        "to_model": fallback,
                        "rest_s": round(seconds),
                        "reason": str(error)[:300],
                        "text": f"{model_key} {why} ({str(error)[:160]}); using {fallback} {until}",
                    },
                )
                model_key = fallback
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
        patience_s: float | None = None,
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
        if patience_s is not None and patience_s <= self.config.llm.rotation_patience_s:
            retry = retry.model_copy(update={"max_attempts": min(retry.max_attempts, 2)})
        return await with_retries(
            lambda: provider.chat(prepared, on_text_delta), retry, self._sleep, on_retry, patience_s
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
