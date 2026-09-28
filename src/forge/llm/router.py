"""Routes each role to its configured model, with redaction, retries, fallback and cost (spec §5.2, §5.3)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from forge.config import ROLES, ForgeConfig, Secrets
from forge.errors import ConfigError, LLMError
from forge.llm.azure_openai import AzureOpenAIProvider
from forge.llm.base import ChatRequest, LLMProvider, LLMResponse, TextDeltaCallback
from forge.llm.cost import CostTracker
from forge.llm.retry import Sleeper, with_retries
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
    ) -> None:
        self.config = config
        self._secrets = secrets
        self._provider_factory = provider_factory or self._create_azure_provider
        self._providers: dict[str, LLMProvider] = {}
        self._redactor = redactor
        self._sleep = sleep
        self._on_notice = on_notice
        self.role_models: dict[str, str | None] = {role: getattr(config.llm.roles, role) for role in ROLES}
        self.cost = CostTracker(config.llm.models, config.limits.session_budget_usd)

    # --- role/model selection (config defaults, changed per session with /model) ---

    def model_for_role(self, role: str) -> str:
        if role not in self.role_models:
            raise ConfigError(f"Unknown role '{role}'. Roles: {', '.join(ROLES)}")
        model_key = self.role_models[role]
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

    def provider(self, model_key: str) -> LLMProvider:
        if model_key not in self._providers:
            self._providers[model_key] = self._provider_factory(model_key)
        return self._providers[model_key]

    def _create_azure_provider(self, model_key: str) -> LLMProvider:
        model = self.config.llm.models[model_key]
        return AzureOpenAIProvider(model_key, model, self.config.llm.providers.azure, self._secrets)

    # --- calls ---

    async def chat(
        self, role: str, request: ChatRequest, on_text_delta: TextDeltaCallback | None = None
    ) -> LLMResponse:
        self.cost.check_budget()
        model_key = self.model_for_role(role)
        try:
            response = await self._call_with_retries(role, model_key, request, on_text_delta)
        except LLMError as error:
            fallback = self.role_models.get("fallback")
            if not error.retryable or fallback is None or fallback == model_key:
                raise
            await self._notice(
                "fallback",
                {"role": role, "from_model": model_key, "to_model": fallback, "reason": str(error)[:300]},
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
            },
        )
        return response

    async def _call_with_retries(
        self, role: str, model_key: str, request: ChatRequest, on_text_delta: TextDeltaCallback | None
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
                },
            )

        return await with_retries(
            lambda: provider.chat(prepared, on_text_delta), self.config.llm.retry, self._sleep, on_retry
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
