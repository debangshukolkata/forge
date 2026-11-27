"""Gemini translation, usage and error mapping — pure code, no Google call (D-150)."""

from __future__ import annotations

import base64

import pytest
from google.auth import exceptions as auth_exceptions
from google.genai import errors, types

from forge.errors import LLMAuthError, LLMNotFoundError, LLMRateLimitError, LLMServerError
from forge.llm.base import Message, ToolCall, ToolSpec
from forge.llm.gemini_errors import map_gemini_error
from forge.llm.translate_gemini import (
    FOREIGN_CALL_SIGNATURE,
    GeminiStreamAccumulator,
    to_gemini_request,
    to_gemini_tools,
)

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


def test_a_note_added_after_the_answer_stays_last_so_the_request_never_ends_on_the_model() -> None:
    """D-664 (office, 2026-11-26): the leftover review's note came after the final answer and was moved into the
    system instruction; Gemini refused the request: 'Requests ending with a model turn are not supported'."""
    messages = [
        Message.system("be brief"),
        Message.user("fix it"),
        Message(role="assistant", content="Done: copy these files."),
        Message.system("Name the temporary changes."),
    ]
    system, contents = to_gemini_request(messages, "gemini")
    assert system == "be brief"
    assert [content.role for content in contents] == ["user", "model", "user"]
    assert "Name the temporary changes." in (contents[-1].parts or [])[0].text
    after_results = [
        Message.user("read"),
        Message(
            role="assistant",
            tool_calls=[ToolCall(id="a", name="read_file", raw_arguments="{}", arguments={})],
        ),
        Message.tool_result("a", "X"),
        Message.system("a note after a result"),
    ]
    system, contents = to_gemini_request(after_results, "gemini")
    # D-670 (office, 2026-11-27): text joined to a turn of tool results made Gemini refuse the next call; after results
    # a note goes to the system instruction, as before D-664, and the results' turn holds results only
    assert [content.role for content in contents] == ["user", "model", "user"]
    assert all(part.function_response for part in contents[-1].parts or [])
    assert system == "a note after a result"


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
    # A different model never gets another model's signatures back, only the documented placeholder (D-643).
    _, other = to_gemini_request([Message.user("go"), replay], "other-model")
    assert (other[1].parts or [])[0].thought_signature == FOREIGN_CALL_SIGNATURE
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


def test_a_request_with_only_instructions_still_has_a_user_turn() -> None:
    # Gemini answers "contents are required" to an empty conversation (Argon as builder, office laptop, 2026-10-16).
    system, contents = to_gemini_request([Message.system("Write one short sentence.")], "gemini4argon")
    assert system is None
    assert len(contents) == 1 and contents[0].role == "user"
    assert contents[0].parts is not None and contents[0].parts[0].text == "Write one short sentence."


async def test_a_refused_request_names_the_shape_of_what_was_sent_never_its_text() -> None:
    """D-669 (office, 2026-11-26): 'Requests ending with a model turn' came back although the translated request ends on
    a user turn here; the error now says which turns and parts were sent, so the next photograph shows the cause."""
    from types import SimpleNamespace

    from forge.errors import LLMError
    from forge.llm.base import ChatRequest
    from forge.llm.gemini import GeminiProvider

    refused = errors.ClientError(
        400,
        {
            "error": {
                "code": 400,
                "message": "Requests ending with a model turn are not supported.",
                "status": "INVALID_ARGUMENT",
            }
        },
    )

    async def generate_content(**_: object) -> None:
        raise refused

    provider = GeminiProvider.__new__(GeminiProvider)
    provider.model_key, provider.model_name = "gemini4hydrogen", "gemini-4-hydrogen"
    provider.model = SimpleNamespace(max_output=1000)  # type: ignore[assignment]
    provider._client = SimpleNamespace(
        aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content))
    )  # type: ignore[assignment]
    messages = [
        Message.system("be brief"),
        Message.user("the secret plan"),
        Message(
            role="assistant",
            tool_calls=[ToolCall(id="a", name="read_file", raw_arguments="{}", arguments={})],
        ),
        Message.tool_result("a", "file text"),
        Message.system("a note"),
    ]
    with pytest.raises(LLMError) as raised:
        await provider.chat(ChatRequest(messages=messages))
    text = str(raised.value)
    assert "Requests ending with a model turn" in text
    assert "last turns sent: user[text] model[call] user[result]" in text
    assert "secret plan" not in text and "file text" not in text
