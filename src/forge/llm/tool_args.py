"""Parsing (and light repair) of tool-call arguments produced by the model (spec §5.3)."""

from __future__ import annotations

import json
import re
from typing import Any

from forge.llm.base import Message, ToolCall

_CODE_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)
_TRAILING_COMMA = re.compile(r",\s*([}\]])")


def parse_tool_arguments(raw: str) -> tuple[dict[str, Any] | None, str | None]:
    """Returns (arguments, None) on success or (None, error message) on failure.

    Repairs only mistakes that can't change meaning: code fences, trailing commas, empty input."""
    candidates = [raw]
    fenced = _CODE_FENCE.match(raw)
    if fenced:
        candidates.append(fenced.group(1))
    candidates.append(_TRAILING_COMMA.sub(r"\1", candidates[-1]))

    last_error = ""
    for candidate in candidates:
        if not candidate.strip():
            return {}, None
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError as error:
            last_error = f"{error.msg} at line {error.lineno} column {error.colno}"
            continue
        if isinstance(value, dict):
            return value, None
        last_error = f"arguments must be a JSON object, got {type(value).__name__}"
    return None, last_error


def make_tool_call(call_id: str, name: str, raw_arguments: str) -> ToolCall:
    arguments, error = parse_tool_arguments(raw_arguments)
    return ToolCall(
        id=call_id, name=name, raw_arguments=raw_arguments, arguments=arguments, parse_error=error
    )


def parse_error_result(call: ToolCall) -> Message:
    """The tool result sent back when arguments couldn't be parsed, so the model can retry."""
    return Message.tool_result(
        call.id,
        f"Error: the arguments for tool '{call.name}' are not valid JSON ({call.parse_error}). "
        "Call the tool again with a single valid JSON object matching its schema.",
    )
