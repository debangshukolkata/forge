"""Gemini translation, usage and error mapping — pure code, no Google call (D-150)."""

from __future__ import annotations

import base64

import pytest
from google.auth import exceptions as auth_exceptions
from google.genai import errors, types

from forge.errors import LLMAuthError, LLMNotFoundError, LLMRateLimitError, LLMServerError
from forge.llm.base import Message, ToolCall, ToolSpec
from forge.llm.gemini_errors import map_gemini_error
from forge.llm.translate_gemini import GeminiStreamAccumulator, to_gemini_request, to_gemini_tools

PNG = base64.b64encode(b"\x89PNG-bytes").decode()


def chunk(*parts: types.Part, finish: str | None = None, usage: dict[str, int] | None = None):
    candidate = types.Candidate(
        content=types.Content(role="model", parts=list(parts)),
        finish_reason=types.FinishReason(finish) if finish else None,
    )
    return types.GenerateContentResponse(
        candidates=[candidate],
        model_version="gemini-2.5-pro",
        usage_metadata=types.GenerateContentResponseUsageMetadata(**usage) if usage else None,
    )


def test_tool_results_merge_into_one_user_turn_matched_by_name() -> None:
    messages = [
        Message.system("be brief"),
        Message.user("read two files"),
        Message(
            role="assistant",
            tool_calls=[
                ToolCall(id="a", name="read_file", raw_arguments='{"path":"x"}', arguments={"path": "x"}),
                ToolCall(id="b", name="read_file", raw_arguments='{"path":"y"}', arguments={"path": "y"}),
            ],
        ),
        Message.tool_result("a", "X"),
        Message.tool_result("b", "Y"),
    ]
    system, contents = to_gemini_request(messages, "gemini")
    assert system == "be brief"
    assert [content.role for content in contents] == ["user", "model", "user"]
    responses = contents[2].parts or []
    assert [part.function_response.name for part in responses if part.function_response] == ["read_file"] * 2
    assert responses[1].function_response.response == {"output": "Y"}


def test_image_data_url_becomes_inline_bytes() -> None:
    message = Message(role="user", content="what is this", images=[f"data:image/png;base64,{PNG}"])
    _, contents = to_gemini_request([message], "gemini")
    blob = (contents[0].parts or [])[1].inline_data
    assert blob is not None and blob.mime_type == "image/png" and blob.data == b"\x89PNG-bytes"


def test_tools_use_the_json_schema_field_untouched() -> None:
    schema = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    declaration = to_gemini_tools([ToolSpec(name="read_file", description="d", parameters=schema)])[0]
    assert (declaration.function_declarations or [])[0].parameters_json_schema == schema


def test_function_call_response_round_trips_with_thought_signature() -> None:
    signature = b"sig-bytes"
    accumulator = GeminiStreamAccumulator("gemini")
    accumulator.add_chunk(chunk(types.Part(text="thinking...", thought=True)))
    accumulator.add_chunk(
        chunk(
            types.Part(
                function_call=types.FunctionCall(name="read_file", args={"path": "config.yaml"}),
                thought_signature=signature,
            ),
            finish="STOP",
            usage={"prompt_token_count": 10, "candidates_token_count": 5, "thoughts_token_count": 7},
        )
    )
    response = accumulator.to_response()
    assert response.finish_reason == "tool_calls"
    assert response.tool_calls[0].arguments == {"path": "config.yaml"}
    assert response.usage.output_tokens == 12 and response.usage.reasoning_tokens == 7
    assert response.text == ""  # the thought summary is not the answer

    replay = response.to_message("gemini")
    _, contents = to_gemini_request([Message.user("go"), replay], "gemini")
    assert (contents[1].parts or [])[0].thought_signature == signature
    # A different model never gets another model's signatures back.
    _, other = to_gemini_request([Message.user("go"), replay], "other-model")
    assert (other[1].parts or [])[0].thought_signature is None
    assert (other[1].parts or [])[0].function_call.args == {"path": "config.yaml"}


def test_streamed_text_fragments_are_joined_and_max_tokens_is_length() -> None:
    accumulator = GeminiStreamAccumulator("gemini")
    seen = [accumulator.add_chunk(chunk(types.Part(text=text)))[0] for text in ("Hel", "lo")]
    accumulator.add_chunk(chunk(finish="MAX_TOKENS"))
    response = accumulator.to_response()
    assert seen == ["Hel", "lo"] and response.text == "Hello" and response.finish_reason == "length"


def test_error_mapping() -> None:
    assert isinstance(map_gemini_error(auth_exceptions.DefaultCredentialsError("none")), LLMAuthError)
    assert "gcloud auth application-default login" in str(
        map_gemini_error(auth_exceptions.DefaultCredentialsError("none"))
    )
    assert isinstance(
        map_gemini_error(errors.ClientError(404, {"error": {"message": "nope"}})), LLMNotFoundError
    )
    assert isinstance(
        map_gemini_error(errors.ClientError(429, {"error": {"message": "slow"}})), LLMRateLimitError
    )
    assert map_gemini_error(errors.ServerError(503, {"error": {"message": "down"}})).retryable
    assert isinstance(map_gemini_error(errors.ServerError(500, {"error": {"message": "x"}})), LLMServerError)


@pytest.mark.parametrize("effort", ["minimal", "low", "medium", "high"])
def test_every_effort_has_a_thinking_budget(effort: str) -> None:
    from forge.llm.translate_gemini import THINKING_BUDGETS

    assert THINKING_BUDGETS[effort] >= 128
