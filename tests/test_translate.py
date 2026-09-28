"""Tool-call translation for both Azure APIs (M1 acceptance)."""

from __future__ import annotations

from forge.llm.base import Message, ToolCall, ToolSpec
from forge.llm.tool_args import make_tool_call, parse_tool_arguments
from forge.llm.translate_chat import (
    ChatStreamAccumulator,
    from_chat_completion,
    to_chat_messages,
    to_chat_tools,
)
from forge.llm.translate_responses import from_responses_output, to_responses_input, to_responses_tools
from tests.helpers import function_call_output, responses_body, text_output

CALL = ToolCall(
    id="call_1", name="read_file", raw_arguments='{"path": "app.py"}', arguments={"path": "app.py"}
)
CONVERSATION = [
    Message.system("You are Forge."),
    Message.user("Open app.py"),
    Message(role="assistant", content="Reading it.", tool_calls=[CALL]),
    Message.tool_result("call_1", "print('hi')"),
]
TOOL = ToolSpec(name="read_file", description="Read a file", parameters={"type": "object", "properties": {}})


def test_messages_to_responses_input() -> None:
    items = to_responses_input(CONVERSATION, "gpt51")

    assert items == [
        {"role": "system", "content": "You are Forge."},
        {"role": "user", "content": "Open app.py"},
        {"role": "assistant", "content": "Reading it."},
        {
            "type": "function_call",
            "call_id": "call_1",
            "name": "read_file",
            "arguments": '{"path": "app.py"}',
        },
        {"type": "function_call_output", "call_id": "call_1", "output": "print('hi')"},
    ]


def test_provider_items_replayed_only_to_the_model_that_made_them() -> None:
    reasoning = {"type": "reasoning", "id": "rs_1", "encrypted_content": "opaque"}
    message = Message(
        role="assistant", tool_calls=[CALL], provider_items=[reasoning], provider_items_model="gpt51"
    )

    assert to_responses_input([message], "gpt51") == [reasoning]
    assert to_responses_input([message], "gpt41")[0]["type"] == "function_call"


def test_messages_to_chat() -> None:
    wire = to_chat_messages(CONVERSATION)

    assert wire[2] == {
        "role": "assistant",
        "content": "Reading it.",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "read_file", "arguments": '{"path": "app.py"}'},
            }
        ],
    }
    assert wire[3] == {"role": "tool", "tool_call_id": "call_1", "content": "print('hi')"}


def test_tool_specs_for_both_apis() -> None:
    assert to_responses_tools([TOOL])[0]["name"] == "read_file"
    assert to_chat_tools([TOOL])[0]["function"]["name"] == "read_file"


def test_responses_output_with_tool_call() -> None:
    body = responses_body([text_output("Let me look."), function_call_output("read_file", '{"path":"a.py"}')])

    response = from_responses_output(body)

    assert response.text == "Let me look."
    assert response.tool_calls[0].arguments == {"path": "a.py"}
    assert response.finish_reason == "tool_calls"
    assert response.usage.cached_input_tokens == 40
    assert response.provider_items == body["output"]


def test_incomplete_response_maps_to_length() -> None:
    body = responses_body([text_output("partial")])
    body["status"] = "incomplete"
    body["incomplete_details"] = {"reason": "max_output_tokens"}

    assert from_responses_output(body).finish_reason == "length"


def test_chat_completion_with_tool_call() -> None:
    completion = {
        "model": "gpt-4.1",
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": None,
                    "tool_calls": [
                        {"id": "c9", "function": {"name": "read_file", "arguments": '{"path":"b.py"}'}}
                    ],
                },
            }
        ],
        "usage": {"prompt_tokens": 9, "completion_tokens": 3},
    }

    response = from_chat_completion(completion)

    assert response.tool_calls[0].id == "c9"
    assert response.tool_calls[0].arguments == {"path": "b.py"}
    assert response.finish_reason == "tool_calls"


def test_chat_stream_accumulator_joins_fragments() -> None:
    accumulator = ChatStreamAccumulator()
    chunks = [
        {"model": "m", "choices": [{"delta": {"content": "Hi "}}]},
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {"index": 0, "id": "c1", "function": {"name": "read_", "arguments": '{"pa'}}
                        ]
                    }
                }
            ]
        },
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [{"index": 0, "function": {"name": "file", "arguments": 'th":"x"}'}}]
                    }
                }
            ]
        },
        {"choices": [{"delta": {}, "finish_reason": "tool_calls"}]},
        {"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 7}},
    ]

    texts = [accumulator.add_chunk(chunk) for chunk in chunks]
    response = from_chat_completion(accumulator.to_completion())

    assert texts[0] == "Hi "
    assert response.tool_calls[0].name == "read_file"
    assert response.tool_calls[0].arguments == {"path": "x"}
    assert response.usage.output_tokens == 7


def test_tool_argument_repairs() -> None:
    assert parse_tool_arguments('```json\n{"a": 1}\n```') == ({"a": 1}, None)
    assert parse_tool_arguments('{"a": [1, 2,],}') == ({"a": [1, 2]}, None)
    assert parse_tool_arguments("") == ({}, None)


def test_malformed_arguments_keep_raw_text_and_error() -> None:
    call = make_tool_call("c1", "write_file", '{"path": "a.py", "content": ')

    assert call.arguments is None
    assert call.parse_error is not None
    assert call.raw_arguments.startswith('{"path"')
