"""Token counting with the vendored o200k_base encoding (spec §5.4, DECISIONS D-015)."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import tiktoken

from forge.llm.base import Message, ToolSpec

VENDORED_TIKTOKEN_DIR = Path(__file__).resolve().parent.parent / "data" / "tiktoken"

# Per-message framing tokens the API adds around each message (role markers etc.).
MESSAGE_OVERHEAD_TOKENS = 4
REQUEST_OVERHEAD_TOKENS = 3


@lru_cache(maxsize=1)
def _encoding() -> tiktoken.Encoding:
    # The laptop is offline: always load the encoding from the package, never from the internet.
    os.environ["TIKTOKEN_CACHE_DIR"] = str(VENDORED_TIKTOKEN_DIR)
    return tiktoken.get_encoding("o200k_base")


def count_text_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_encoding().encode(text, disallowed_special=()))


# A high-detail image of up to 2048 px (what view_image sends) costs about this much (spec §13A.1).
IMAGE_TOKENS = 1105


def count_message_tokens(message: Message) -> int:
    total = MESSAGE_OVERHEAD_TOKENS + count_text_tokens(message.content)
    for call in message.tool_calls:
        total += (
            count_text_tokens(call.name) + count_text_tokens(call.raw_arguments) + MESSAGE_OVERHEAD_TOKENS
        )
    return total + IMAGE_TOKENS * len(message.images)


def count_tools_tokens(tools: list[ToolSpec]) -> int:
    return sum(count_text_tokens(json.dumps(tool.model_dump(), separators=(",", ":"))) for tool in tools)


def count_request_tokens(messages: list[Message], tools: list[ToolSpec] | None = None) -> int:
    """Estimate of the prompt size. Encrypted reasoning items are not counted: their size is opaque."""
    return (
        REQUEST_OVERHEAD_TOKENS
        + sum(count_message_tokens(m) for m in messages)
        + count_tools_tokens(tools or [])
    )


def head_and_tail(text: str, max_tokens: int) -> tuple[str, str, int]:
    """Splits text that exceeds max_tokens into (head, tail, omitted token count); omitted is 0 and
    head is the whole text when it already fits."""
    tokens = _encoding().encode(text, disallowed_special=())
    if len(tokens) <= max_tokens:
        return text, "", 0
    half = max_tokens // 2
    encoding = _encoding()
    return encoding.decode(tokens[:half]), encoding.decode(tokens[-half:]), len(tokens) - 2 * half
