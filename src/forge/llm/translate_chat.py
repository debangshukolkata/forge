"""Translation between Forge's messages and the Chat Completions wire format (fallback API)."""

from __future__ import annotations

from typing import Any

from forge.llm.base import FinishReason, LLMResponse, Message, ToolSpec, Usage
from forge.llm.tool_args import make_tool_call

_FINISH_REASONS: dict[str, FinishReason] = {
    "stop": "stop",
    "tool_calls": "tool_calls",
    "function_call": "tool_calls",
    "length": "length",
    "content_filter": "content_filter",
}


def to_chat_messages(messages: list[Message]) -> list[dict[str, Any]]:
    wire: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "tool":
            wire.append({"role": "tool", "tool_call_id": message.tool_call_id, "content": message.content})
        elif message.role == "assistant":
            entry: dict[str, Any] = {"role": "assistant", "content": message.content or None}
            if message.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": call.raw_arguments},
                    }
                    for call in message.tool_calls
                ]
            wire.append(entry)
        elif message.role == "user" and message.images:
            parts: list[dict[str, Any]] = [{"type": "text", "text": message.content}]
            parts += [
                {"type": "image_url", "image_url": {"url": url, "detail": "high"}} for url in message.images
            ]
            wire.append({"role": "user", "content": parts})
        else:
            wire.append({"role": message.role, "content": message.content})
    return wire


def to_chat_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
        }
        for t in tools
    ]


def from_chat_completion(completion: dict[str, Any]) -> LLMResponse:
    choice = (completion.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    tool_calls = [
        make_tool_call(call["id"], call["function"]["name"], call["function"].get("arguments") or "")
        for call in message.get("tool_calls") or []
    ]
    return LLMResponse(
        text=message.get("content") or message.get("refusal") or "",
        tool_calls=tool_calls,
        usage=chat_usage(completion.get("usage") or {}),
        finish_reason=_FINISH_REASONS.get(choice.get("finish_reason") or "", "other"),
        served_model=completion.get("model") or "",
    )


def chat_usage(usage: dict[str, Any]) -> Usage:
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    return Usage(
        input_tokens=usage.get("prompt_tokens") or 0,
        cached_input_tokens=prompt_details.get("cached_tokens") or 0,
        output_tokens=usage.get("completion_tokens") or 0,
        reasoning_tokens=completion_details.get("reasoning_tokens") or 0,
    )


class ChatStreamAccumulator:
    """Rebuilds a complete chat.completion from streamed chunks (tool calls arrive in fragments)."""

    def __init__(self) -> None:
        self.text_parts: list[str] = []
        self.tool_calls: dict[int, dict[str, str]] = {}
        self.finish_reason: str | None = None
        self.model = ""
        self.usage: dict[str, Any] = {}

    def add_chunk(self, chunk: dict[str, Any]) -> str:
        """Returns any new text in this chunk."""
        self.model = chunk.get("model") or self.model
        if chunk.get("usage"):
            self.usage = chunk["usage"]
        new_text = ""
        for choice in chunk.get("choices") or []:
            delta = choice.get("delta") or {}
            if delta.get("content"):
                new_text += delta["content"]
            for fragment in delta.get("tool_calls") or []:
                slot = self.tool_calls.setdefault(
                    fragment.get("index", 0), {"id": "", "name": "", "arguments": ""}
                )
                slot["id"] = fragment.get("id") or slot["id"]
                function = fragment.get("function") or {}
                slot["name"] += function.get("name") or ""
                slot["arguments"] += function.get("arguments") or ""
            if choice.get("finish_reason"):
                self.finish_reason = choice["finish_reason"]
        self.text_parts.append(new_text)
        return new_text

    def to_completion(self) -> dict[str, Any]:
        tool_calls = [
            {
                "id": slot["id"],
                "type": "function",
                "function": {"name": slot["name"], "arguments": slot["arguments"]},
            }
            for _, slot in sorted(self.tool_calls.items())
        ]
        return {
            "model": self.model,
            "usage": self.usage,
            "choices": [
                {
                    "finish_reason": self.finish_reason,
                    "message": {"content": "".join(self.text_parts), "tool_calls": tool_calls or None},
                }
            ],
        }
