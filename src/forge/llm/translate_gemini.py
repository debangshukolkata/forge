"""Translation between Forge's messages and the google-genai (Vertex AI) types (D-150)."""

from __future__ import annotations

import base64
import json
import uuid
from typing import Any

from google.genai import types

from forge.llm.base import FinishReason, LLMResponse, Message, ToolSpec, Usage
from forge.llm.tool_args import make_tool_call

# Thinking budgets (tokens) for Forge's effort names. Only the integer budget is accepted on the user's Vertex
# API version; the newer thinking_level enum is rejected as "not supported by this model" (verified live).
THINKING_BUDGETS = {"minimal": 128, "low": 1024, "medium": 8192, "high": 24576}

_FINISH_REASONS: dict[str, FinishReason] = {
    "STOP": "stop",
    "MAX_TOKENS": "length",
    "SAFETY": "content_filter",
    "RECITATION": "content_filter",
    "BLOCKLIST": "content_filter",
    "PROHIBITED_CONTENT": "content_filter",
    "SPII": "content_filter",
    "IMAGE_SAFETY": "content_filter",
}

PROVIDER_ITEM_TYPE = "gemini_content"


def split_data_url(data_url: str) -> tuple[str, bytes]:
    header, _, payload = data_url.partition(",")
    mime_type = header.removeprefix("data:").split(";")[0] or "application/octet-stream"
    return mime_type, base64.b64decode(payload)


def to_gemini_request(messages: list[Message], model_key: str) -> tuple[str | None, list[types.Content]]:
    """Returns (system instruction, conversation). Gemini wants tool results as function_response parts of a
    user turn, matched to calls by name, so consecutive tool messages are merged into one turn."""
    system_parts: list[str] = []
    contents: list[types.Content] = []
    call_names: dict[str, str] = {}
    pending_results: list[types.Part] = []

    def flush_results() -> None:
        if pending_results:
            contents.append(types.Content(role="user", parts=list(pending_results)))
            pending_results.clear()

    for message in messages:
        if message.role == "tool":
            name = call_names.get(message.tool_call_id or "", "unknown_tool")
            pending_results.append(
                types.Part.from_function_response(name=name, response={"output": message.content})
            )
            continue
        flush_results()
        if message.role == "system":
            system_parts.append(message.content)
        elif message.role == "assistant":
            for call in message.tool_calls:
                call_names[call.id] = call.name
            contents.append(_assistant_content(message, model_key))
        else:
            parts = [types.Part(text=message.content)] if message.content else []
            for url in message.images:
                mime_type, data = split_data_url(url)
                parts.append(types.Part.from_bytes(data=data, mime_type=mime_type))
            contents.append(types.Content(role="user", parts=parts or [types.Part(text="")]))
    flush_results()
    return ("\n\n".join(system_parts) or None), contents


def _assistant_content(message: Message, model_key: str) -> types.Content:
    # The model's own parts carry thought signatures that Gemini needs back with its function calls to keep
    # its reasoning across turns; they are replayed only to the model that produced them.
    if message.provider_items and message.provider_items_model == model_key:
        for item in message.provider_items:
            if item.get("type") == PROVIDER_ITEM_TYPE:
                return types.Content.model_validate_json(json.dumps(item["content"]))
    parts: list[types.Part] = [types.Part(text=message.content)] if message.content else []
    for call in message.tool_calls:
        parts.append(types.Part.from_function_call(name=call.name, args=call.arguments or {}))
    return types.Content(role="model", parts=parts or [types.Part(text="")])


def to_gemini_tools(tools: list[ToolSpec]) -> list[types.Tool]:
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name=tool.name, description=tool.description, parameters_json_schema=tool.parameters
                )
                for tool in tools
            ]
        )
    ]


class GeminiStreamAccumulator:
    """Folds streamed chunks (one chunk when not streaming) into one LLMResponse.

    Text arrives in fragments, function calls arrive whole. Thought summaries stay apart from the answer."""

    def __init__(self, model_key: str) -> None:
        self.model_key = model_key
        self.parts: list[types.Part] = []
        self.served_model = ""
        self.finish_reason = ""
        self.blocked = False
        self.usage: types.GenerateContentResponseUsageMetadata | None = None

    def add_chunk(self, chunk: types.GenerateContentResponse) -> tuple[str, str]:
        """Returns (new answer text, new thought-summary text) in this chunk."""
        self.served_model = chunk.model_version or self.served_model
        if chunk.usage_metadata is not None:
            self.usage = chunk.usage_metadata
        if chunk.prompt_feedback is not None and chunk.prompt_feedback.block_reason:
            self.blocked = True
        text = thought = ""
        for candidate in chunk.candidates or []:
            if candidate.finish_reason:
                self.finish_reason = candidate.finish_reason.value
            for part in (candidate.content.parts if candidate.content else None) or []:
                self.parts.append(part)
                if part.text and part.thought:
                    thought += part.text
                elif part.text:
                    text += part.text
        return text, thought

    def to_response(self) -> LLMResponse:
        answer_parts = [part for part in self.parts if not part.thought]
        text = "".join(part.text for part in answer_parts if part.text)
        tool_calls = [
            make_tool_call(
                part.function_call.id or f"call_{uuid.uuid4().hex[:12]}",
                part.function_call.name or "",
                json.dumps(part.function_call.args or {}),
            )
            for part in answer_parts
            if part.function_call
        ]
        finish: FinishReason = "content_filter" if self.blocked and not self.parts else "other"
        if self.finish_reason:
            finish = _FINISH_REASONS.get(self.finish_reason, "other")
        if tool_calls and finish == "stop":
            finish = "tool_calls"
        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            usage=gemini_usage(self.usage),
            finish_reason=finish,
            served_model=self.served_model,
            provider_items=self._provider_items(answer_parts),
        )

    def _provider_items(self, answer_parts: list[types.Part]) -> list[dict[str, Any]] | None:
        if not answer_parts:
            return None
        content = types.Content(role="model", parts=_merge_text_parts(answer_parts))
        return [{"type": PROVIDER_ITEM_TYPE, "content": content.model_dump(mode="json", exclude_none=True)}]


def _merge_text_parts(parts: list[types.Part]) -> list[types.Part]:
    """Streaming splits one answer into many text parts; fold neighbours back together."""
    merged: list[types.Part] = []
    for part in parts:
        previous = merged[-1] if merged else None
        if previous is not None and previous.text is not None and part.text is not None:
            merged[-1] = types.Part(
                text=previous.text + part.text,
                thought_signature=part.thought_signature or previous.thought_signature,
            )
        else:
            merged.append(part)
    return merged


def gemini_usage(usage: types.GenerateContentResponseUsageMetadata | None) -> Usage:
    if usage is None:
        return Usage()
    thoughts = usage.thoughts_token_count or 0
    # Gemini reports thinking apart from the answer; Forge's output_tokens includes it (as with OpenAI).
    return Usage(
        input_tokens=usage.prompt_token_count or 0,
        cached_input_tokens=usage.cached_content_token_count or 0,
        output_tokens=(usage.candidates_token_count or 0) + thoughts,
        reasoning_tokens=thoughts,
    )
