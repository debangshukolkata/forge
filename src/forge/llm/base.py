"""Provider-independent message, tool and response types (spec §5.1).

Every adapter translates between these and its provider's wire format, so the agent loop,
context manager and UIs never see provider specifics.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]


class ToolCall(BaseModel):
    id: str
    name: str
    raw_arguments: str
    # None when raw_arguments isn't valid JSON; parse_error then says why (bounced back to the model).
    arguments: dict[str, Any] | None = None
    parse_error: str | None = None


class Message(BaseModel):
    role: Role
    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None  # set on role="tool"
    # Opaque Responses-API output items (incl. encrypted reasoning) that let the same model keep its
    # reasoning across turns. Replayed only to the model that produced them; safe to drop.
    provider_items: list[dict[str, Any]] | None = None
    provider_items_model: str | None = None
    # Data URLs of images attached to a user message. Only view_image and the eval judge build these
    # (spec §13A.1: images enter the model's context only through view_image); never persisted in history.
    images: list[str] = Field(default_factory=list)

    @classmethod
    def system(cls, content: str) -> Message:
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> Message:
        return cls(role="user", content=content)

    @classmethod
    def tool_result(cls, tool_call_id: str, content: str) -> Message:
        return cls(role="tool", tool_call_id=tool_call_id, content=content)


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema of the arguments object


class Usage(BaseModel):
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            reasoning_tokens=self.reasoning_tokens + other.reasoning_tokens,
        )


FinishReason = Literal["stop", "tool_calls", "length", "content_filter", "other"]


class LLMResponse(BaseModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage = Usage()
    finish_reason: FinishReason = "stop"
    served_model: str = ""  # what the provider says actually answered (deployment names can mislead)
    provider_items: list[dict[str, Any]] | None = None
    citations: list[dict[str, str]] = Field(default_factory=list)  # url_citation annotations (hosted search)

    def to_message(self, model_key: str) -> Message:
        return Message(
            role="assistant",
            content=self.text,
            tool_calls=self.tool_calls,
            provider_items=self.provider_items,
            provider_items_model=model_key if self.provider_items else None,
        )


class ChatRequest(BaseModel):
    messages: list[Message]
    tools: list[ToolSpec] = Field(default_factory=list)
    max_output_tokens: int | None = None
    reasoning_effort: str | None = None
    parallel_tool_calls: bool = True
    # Tools the provider runs itself (Responses API), e.g. "web_search". Only used by Forge's search tool.
    hosted_tools: list[str] = Field(default_factory=list)


TextDeltaCallback = Callable[[str], Awaitable[None]]


class LLMProvider(Protocol):
    model_key: str

    async def chat(self, request: ChatRequest, on_text_delta: TextDeltaCallback | None = None) -> LLMResponse:
        """One model call. Streams text through on_text_delta when given. Raises forge.errors.LLMError."""
        ...
