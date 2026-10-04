"""Gemini adapter: Vertex AI through the google-genai SDK, authenticated by Application Default
Credentials (D-150).

Forge never stores or reads Google credentials; only the project and location names come from .env."""

from __future__ import annotations

from typing import Any, cast

from google import genai
from google.genai import types

from forge.config import GeminiProviderConfig, ModelConfig, Secrets
from forge.errors import LLMError
from forge.llm.base import ChatRequest, LLMResponse, TextDeltaCallback
from forge.llm.gemini_errors import SDK_ERRORS, map_gemini_error
from forge.llm.translate_gemini import (
    THINKING_BUDGETS,
    GeminiStreamAccumulator,
    to_gemini_request,
    to_gemini_tools,
)


class GeminiProvider:
    def __init__(
        self, model_key: str, model: ModelConfig, provider_config: GeminiProviderConfig, secrets: Secrets
    ) -> None:
        self.model_key = model_key
        self.model = model
        self.model_name = model.model_name or ""
        try:
            self._client = genai.Client(
                vertexai=True,
                project=secrets.require(provider_config.project_env),
                location=secrets.require(provider_config.location_env),
                http_options=types.HttpOptions(
                    timeout=int(provider_config.timeout_s * 1000),
                    # Forge's own retry layer reports retries to the UI; the SDK must not retry silently.
                    retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
        except SDK_ERRORS as error:  # no credentials at all fails here, before any request
            raise map_gemini_error(error) from error

    async def chat(self, request: ChatRequest, on_text_delta: TextDeltaCallback | None = None) -> LLMResponse:
        if request.hosted_tools:
            raise LLMError(f"{', '.join(request.hosted_tools)} is only available on the Azure Responses API.")
        system_instruction, turns = to_gemini_request(request.messages, self.model_key)
        contents = cast(
            Any, turns
        )  # list[Content] is valid; the SDK's union annotation just can't express it
        config = self._config(request, system_instruction)
        accumulator = GeminiStreamAccumulator(self.model_key)
        thinking = ""
        try:
            if on_text_delta is None:
                response = await self._client.aio.models.generate_content(
                    model=self.model_name, contents=contents, config=config
                )
                accumulator.add_chunk(response)
            else:
                stream = await self._client.aio.models.generate_content_stream(
                    model=self.model_name, contents=contents, config=config
                )
                async for chunk in stream:
                    text, thought = accumulator.add_chunk(chunk)
                    thinking += thought
                    if text:
                        await on_text_delta(text)
        except SDK_ERRORS as error:
            raise map_gemini_error(error) from error
        if request.on_thinking is not None and thinking:
            await request.on_thinking(thinking)
        return accumulator.to_response()

    def _config(self, request: ChatRequest, system_instruction: str | None) -> types.GenerateContentConfig:
        params: dict[str, Any] = {
            "system_instruction": system_instruction,
            "max_output_tokens": request.max_output_tokens or self.model.max_output,
            # Forge's loop owns every tool call; the SDK must never run tools or loop on its own.
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
        }
        if request.tools:
            params["tools"] = to_gemini_tools(request.tools)
        thinking: dict[str, Any] = {}
        if request.reasoning_effort:
            thinking["thinking_budget"] = THINKING_BUDGETS.get(request.reasoning_effort, -1)
        if request.on_thinking is not None:
            thinking["include_thoughts"] = True
        if thinking:
            params["thinking_config"] = types.ThinkingConfig(**thinking)
        return types.GenerateContentConfig(**params)

    async def close(self) -> None:
        await self._client.aio.aclose()
