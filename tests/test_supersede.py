"""A chat message answers open approval cards and questions (D-153); deterministic, no model."""

from __future__ import annotations

import asyncio

import httpx2

from forge.engine.session_host import SessionHost
from forge.protocol.events import EventBus, EventType
from forge.protocol.inputs import SendMessage
from forge.safety.redact import Redactor
from tests.helpers import mocked_router


def _host() -> SessionHost:
    router = mocked_router(lambda request: httpx2.Response(500))
    return SessionHost(router, EventBus(redactor=Redactor()))


async def test_message_declines_open_approval_with_the_message_as_instruction() -> None:
    host = _host()
    waiting = asyncio.create_task(host.approvals.request({"tool": "propose_lessons"}))
    await asyncio.sleep(0)  # let the request register
    await host.submit(SendMessage(text="launch the app instead"))
    answer = await asyncio.wait_for(waiting, timeout=1)
    assert answer.approved is False
    assert answer.instruction == "launch the app instead"
    assert any(e.payload.get("kind") == "request_superseded" for e in host.bus.events_since(0))


async def test_message_answers_open_question_as_free_text() -> None:
    host = _host()
    waiting = asyncio.create_task(host.questions.ask(EventType.QUESTION_ASKED, {"question": "which?"}))
    await asyncio.sleep(0)
    await host.submit(SendMessage(text="the second one"))
    answer = await asyncio.wait_for(waiting, timeout=1)
    assert answer.text == "the second one"


async def test_slash_commands_leave_open_requests_alone() -> None:
    host = _host()
    waiting = asyncio.create_task(host.approvals.request({"tool": "x"}))
    await asyncio.sleep(0)
    await host.submit(SendMessage(text="/lessons"))
    assert not waiting.done()
    waiting.cancel()


def test_build_id_is_stable_and_short() -> None:
    from forge.buildinfo import build_id, describe

    assert build_id() == build_id()
    assert len(build_id()) == 10
    assert build_id() in describe()
