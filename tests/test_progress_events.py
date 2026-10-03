"""Visible progress while the model thinks (D-174): reasoning summaries stream as events; deployments that
refuse summaries still work."""

from __future__ import annotations

import json

import httpx2

from forge.engine.session_host import SessionHost
from forge.llm.base import ChatRequest, Message
from forge.protocol.events import EventBus, EventType
from forge.safety.redact import Redactor
from tests.helpers import error_body, json_response, mocked_router, responses_body, text_output

HELLO = [Message.user("hi")]


def sse(events: list[dict[str, object]]) -> httpx2.Response:
    stream = "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)
    return httpx2.Response(200, content=stream.encode(), headers={"content-type": "text/event-stream"})


def streamed_answer(with_summary: bool) -> httpx2.Response:
    body = responses_body([text_output("ok")])
    events: list[dict[str, object]] = []
    if with_summary:
        events.append(
            {
                "type": "response.reasoning_summary_text.done",
                "text": "**Checking the routes** I need to see how errors are shaped.",
                "item_id": "rs_1",
                "output_index": 0,
                "summary_index": 0,
                "sequence_number": 0,
            }
        )
    events.append({"type": "response.completed", "response": body, "sequence_number": len(events)})
    return sse(events)


async def test_reasoning_summaries_reach_the_thinking_callback() -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return streamed_answer(True)

    seen: list[str] = []

    async def thinking(text: str) -> None:
        seen.append(text)

    async def text(_: str) -> None:
        return None

    router = mocked_router(handler)
    request = ChatRequest(messages=HELLO, reasoning_effort="medium", on_thinking=thinking)
    await router.chat("coder", request, text)
    assert bodies[0]["reasoning"] == {"effort": "medium", "summary": "auto"}
    assert seen == ["**Checking the routes** I need to see how errors are shaped."]
    assert "on_thinking" not in json.dumps(bodies[0])  # a local callback is never sent to the service


async def test_a_deployment_that_refuses_summaries_is_retried_without_them() -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if "summary" in body.get("reasoning", {}):
            return json_response(
                400, error_body("invalid_request_error", "Unsupported parameter: reasoning.summary")
            )
        return streamed_answer(False)

    async def thinking(_: str) -> None:
        raise AssertionError("no summary expected")

    async def text(_: str) -> None:
        return None

    router = mocked_router(handler)
    response = await router.chat(
        "coder", ChatRequest(messages=HELLO, reasoning_effort="medium", on_thinking=thinking), text
    )
    assert response.text == "ok"
    assert len(bodies) == 2 and "summary" not in bodies[1]["reasoning"]  # type: ignore[operator]


async def test_the_session_host_publishes_thinking_as_an_event() -> None:
    router = mocked_router(lambda request: httpx2.Response(500))
    host = SessionHost(router, EventBus(redactor=Redactor()))
    await host.stream_thinking("  Reading the routes.  ")
    await host.stream_thinking("   ")  # nothing to show
    events = [e for e in host.bus.events_since(0) if e.type == EventType.THINKING_DELTA]
    assert [e.payload["text"] for e in events] == ["  Reading the routes.  "]
