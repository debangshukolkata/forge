"""Azure OpenAI adapter: Responses API by default, Chat Completions as a fallback (spec §5.1)."""

from __future__ import annotations

from typing import Any

import httpx2  # the openai SDK's HTTP client (a maintained httpx fork)
import openai
from openai import AsyncAzureOpenAI

from forge.config import AzureProviderConfig, ModelConfig, Secrets
from forge.errors import ConfigError, LLMError, LLMNotFoundError
from forge.llm.azure_errors import map_openai_error
from forge.llm.base import ChatRequest, LLMResponse, TextDeltaCallback
from forge.llm.translate_chat import (
    ChatStreamAccumulator,
    from_chat_completion,
    to_chat_messages,
    to_chat_tools,
)
from forge.llm.translate_responses import from_responses_output, to_responses_input, to_responses_tools

# The data-plane deployment-info route only exists on this older api-version.
DEPLOYMENT_INFO_API_VERSION = "2022-12-01"


class AzureOpenAIProvider:
    def __init__(
        self,
        model_key: str,
        model: ModelConfig,
        provider_config: AzureProviderConfig,
        secrets: Secrets,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        self.model_key = model_key
        self.model = model
        if not model.deployment_env:
            raise ConfigError(f"Model '{model_key}' needs deployment_env")
        self.deployment = secrets.require(model.deployment_env)
        self.api = provider_config.api
        self.fell_back_to_chat = False
        self._served_model: str | None = None
        self._client = AsyncAzureOpenAI(
            azure_endpoint=secrets.require(provider_config.endpoint_env),
            api_key=secrets.require(provider_config.api_key_env),
            api_version=secrets.require(provider_config.api_version_env),
            timeout=provider_config.timeout_s,
            max_retries=0,  # Forge's own retry layer honours Retry-After and reports retries to the UI
            http_client=http_client,
        )

    async def chat(self, request: ChatRequest, on_text_delta: TextDeltaCallback | None = None) -> LLMResponse:
        response = await self._chat_with_api_fallback(request, on_text_delta)
        # The Responses API reports the deployment name as the model; deployment names can mislead
        # (here "aicloud-gpt-4o" serves gpt-5.1), so ask Azure what the deployment really serves.
        if response.served_model in ("", self.deployment):
            response.served_model = await self.lookup_served_model() or response.served_model
        return response

    async def _chat_with_api_fallback(
        self, request: ChatRequest, on_text_delta: TextDeltaCallback | None
    ) -> LLMResponse:
        if self.api == "responses":
            try:
                return await self._call_responses(request, on_text_delta)
            except LLMNotFoundError:
                # Older api-versions (and some deployments) have no Responses API; Chat Completions
                # still works. If the deployment itself is wrong, the chat call fails with 404 too.
                self.api = "chat_completions"
                self.fell_back_to_chat = True
        return await self._call_chat(request, on_text_delta)

    async def lookup_served_model(self) -> str | None:
        """The model behind the deployment, from Azure's deployment-info endpoint. Cached; None if unknown."""
        if self._served_model is None:
            try:
                info = await self._client.get(
                    f"/deployments/{self.deployment}",
                    cast_to=httpx2.Response,
                    options={"params": {"api-version": DEPLOYMENT_INFO_API_VERSION}},
                )
                self._served_model = str(info.json().get("model") or "")
            except (openai.OpenAIError, ValueError):
                self._served_model = ""  # not available on every resource; don't ask again
        return self._served_model or None

    async def _call_responses(
        self, request: ChatRequest, on_text_delta: TextDeltaCallback | None
    ) -> LLMResponse:
        params: dict[str, Any] = {
            "model": self.deployment,
            "input": to_responses_input(request.messages, self.model_key),
            "max_output_tokens": request.max_output_tokens or self.model.max_output,
            # Stateless: Forge owns the history (compaction, resume), so nothing is stored server-side.
            "store": False,
        }
        if request.tools:
            params["tools"] = to_responses_tools(request.tools)
            params["parallel_tool_calls"] = request.parallel_tool_calls
        if request.hosted_tools:
            params["tools"] = [*params.get("tools", []), *({"type": t} for t in request.hosted_tools)]
        if request.reasoning_effort:
            params["reasoning"] = {"effort": request.reasoning_effort}
            params["include"] = ["reasoning.encrypted_content"]
        wants_summary = bool(request.on_thinking and request.reasoning_effort and on_text_delta)
        if wants_summary:  # progress while it thinks: short summaries of the reasoning (D-174)
            params["reasoning"] = {**params["reasoning"], "summary": "auto"}
        try:
            if on_text_delta is None:
                response = await self._client.responses.create(**params)
                return from_responses_output(response.model_dump(exclude_none=True))
            try:
                return await self._stream_responses(params, on_text_delta, request.on_thinking)
            except openai.BadRequestError as error:
                if not wants_summary or "summary" not in str(error).lower():
                    raise
                params["reasoning"].pop("summary", None)  # this deployment does not offer summaries
                return await self._stream_responses(params, on_text_delta, None)
        except openai.OpenAIError as error:
            raise map_openai_error(error) from error

    async def _stream_responses(
        self,
        params: dict[str, Any],
        on_text_delta: TextDeltaCallback,
        on_thinking: TextDeltaCallback | None = None,
    ) -> LLMResponse:
        stream = await self._client.responses.create(**params, stream=True)
        final: dict[str, Any] | None = None
        async for event in stream:
            if event.type == "response.output_text.delta":
                await on_text_delta(event.delta)
            elif event.type == "response.reasoning_summary_text.done" and on_thinking is not None:
                await on_thinking(str(getattr(event, "text", "") or ""))
            elif event.type in ("response.completed", "response.incomplete"):
                final = event.response.model_dump(exclude_none=True)
            elif event.type in ("response.failed", "error"):
                raise LLMError(f"Streaming failed: {event.model_dump_json()[:500]}")
        if final is None:
            raise LLMError("Stream ended without a final response")
        return from_responses_output(final)

    async def _call_chat(self, request: ChatRequest, on_text_delta: TextDeltaCallback | None) -> LLMResponse:
        if request.hosted_tools:
            raise LLMError(
                f"{', '.join(request.hosted_tools)} needs the Responses API; this deployment uses "
                f"Chat Completions."
            )
        params: dict[str, Any] = {
            "model": self.deployment,
            "messages": to_chat_messages(request.messages),
            "max_completion_tokens": request.max_output_tokens or self.model.max_output,
        }
        if request.tools:
            params["tools"] = to_chat_tools(request.tools)
            params["parallel_tool_calls"] = request.parallel_tool_calls
        if request.reasoning_effort:
            params["reasoning_effort"] = request.reasoning_effort
        try:
            if on_text_delta is None:
                completion = await self._client.chat.completions.create(**params)
                return from_chat_completion(completion.model_dump(exclude_none=True))
            return await self._stream_chat(params, on_text_delta)
        except openai.OpenAIError as error:
            raise map_openai_error(error) from error

    async def _stream_chat(self, params: dict[str, Any], on_text_delta: TextDeltaCallback) -> LLMResponse:
        stream = await self._client.chat.completions.create(
            **params, stream=True, stream_options={"include_usage": True}
        )
        accumulator = ChatStreamAccumulator()
        async for chunk in stream:
            new_text = accumulator.add_chunk(chunk.model_dump(exclude_none=True))
            if new_text:
                await on_text_delta(new_text)
        return from_chat_completion(accumulator.to_completion())

    async def close(self) -> None:
        await self._client.close()
