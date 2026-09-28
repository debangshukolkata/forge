"""Translation between Forge's messages and the OpenAI/Azure Responses API wire format."""

from __future__ import annotations

from typing import Any

from forge.llm.base import FinishReason, LLMResponse, Message, ToolSpec, Usage
from forge.llm.tool_args import make_tool_call


def to_responses_input(messages: list[Message], model_key: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "user" and message.images:
            parts: list[dict[str, Any]] = [{"type": "input_text", "text": message.content}]
            parts += [{"type": "input_image", "image_url": url, "detail": "high"} for url in message.images]
            items.append({"role": "user", "content": parts})
        elif message.role in ("system", "user"):
            items.append({"role": message.role, "content": message.content})
        elif message.role == "assistant":
            items.extend(_assistant_items(message, model_key))
        elif message.role == "tool":
            items.append(
                {"type": "function_call_output", "call_id": message.tool_call_id, "output": message.content}
            )
    return items


def _assistant_items(message: Message, model_key: str) -> list[dict[str, Any]]:
    # Replaying the model's own items keeps its (encrypted) reasoning; another model can't use them.
    if message.provider_items and message.provider_items_model == model_key:
        return list(message.provider_items)
    items: list[dict[str, Any]] = []
    if message.content:
        items.append({"role": "assistant", "content": message.content})
    for call in message.tool_calls:
        items.append(
            {"type": "function_call", "call_id": call.id, "name": call.name, "arguments": call.raw_arguments}
        )
    return items


def to_responses_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            # Strict mode requires every property to be required; Forge tools have optional arguments.
            "strict": False,
        }
        for tool in tools
    ]


def from_responses_output(response: dict[str, Any]) -> LLMResponse:
    output = response.get("output") or []
    text_parts: list[str] = []
    tool_calls = []
    citations: list[dict[str, str]] = []
    for item in output:
        item_type = item.get("type")
        if item_type == "message":
            for part in item.get("content") or []:
                if part.get("type") == "output_text":
                    text_parts.append(part.get("text", ""))
                    citations += [
                        {"url": a.get("url", ""), "title": a.get("title", "")}
                        for a in part.get("annotations") or []
                        if a.get("type") == "url_citation" and a.get("url")
                    ]
                elif part.get("type") == "refusal":
                    text_parts.append(part.get("refusal", ""))
        elif item_type == "function_call":
            tool_calls.append(make_tool_call(item["call_id"], item["name"], item.get("arguments") or ""))
    return LLMResponse(
        text="".join(text_parts),
        tool_calls=tool_calls,
        usage=_usage(response.get("usage") or {}),
        finish_reason=_finish_reason(response, bool(tool_calls)),
        served_model=response.get("model") or "",
        provider_items=output or None,
        citations=citations,
    )


def _usage(usage: dict[str, Any]) -> Usage:
    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    return Usage(
        input_tokens=usage.get("input_tokens") or 0,
        cached_input_tokens=input_details.get("cached_tokens") or 0,
        output_tokens=usage.get("output_tokens") or 0,
        reasoning_tokens=output_details.get("reasoning_tokens") or 0,
    )


def _finish_reason(response: dict[str, Any], has_tool_calls: bool) -> FinishReason:
    if response.get("status") == "incomplete":
        reason = (response.get("incomplete_details") or {}).get("reason")
        if reason == "max_output_tokens":
            return "length"
        if reason == "content_filter":
            return "content_filter"
        return "other"
    return "tool_calls" if has_tool_calls else "stop"
