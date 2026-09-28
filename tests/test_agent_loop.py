"""Agent-loop failure handling with failures injected at the transport layer (DECISIONS D-008)."""

from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path

import httpx2

from forge.agent.loop import CUT_OFF_NOTE
from forge.engine.events import EventBus, EventType
from forge.engine.inputs import SendMessage
from forge.engine.session_host import SessionHost
from forge.safety.redact import Redactor
from forge.workspace.create import create_workspace
from tests.helpers import mocked_router, reply, responses_body, text_output


async def test_reply_cut_off_at_the_output_limit_is_continued(original_repo: Path, tmp_path: Path) -> None:
    bodies: list[dict[str, object]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        if len(bodies) == 1:  # all output budget went into reasoning: no text, status incomplete
            body = responses_body([])
            body["status"] = "incomplete"
            body["incomplete_details"] = {"reason": "max_output_tokens"}
            return reply(request, body)
        return reply(request, responses_body([text_output("ClaimsAppError, NotFoundError")]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    runner = asyncio.create_task(host.run())
    await host.submit(SendMessage(text="List the error classes."))
    for _ in range(100):
        await asyncio.sleep(0.05)
        if any(e.type == EventType.COST_UPDATED for e in host.bus.events_since(0)):
            break
    runner.cancel()

    assert len(bodies) == 2
    assert bodies[0]["reasoning"] == {"effort": "medium"}
    assert bodies[1]["reasoning"] == {"effort": "low"}  # think less so the answer fits
    assert any(m.role == "system" and m.content == CUT_OFF_NOTE for m in host.history)
    kinds = [e.payload.get("kind") for e in host.bus.events_since(0) if e.type == EventType.NOTICE]
    assert "continuing" in kinds
    assert host.history[-1].content == "ClaimsAppError, NotFoundError"


async def test_cancelling_the_session_mid_turn_ends_it(original_repo: Path, tmp_path: Path) -> None:
    """An Interrupt cancels only the turn; cancelling the session task itself must end run() — swallowing it
    hung the event loop's shutdown (seen as pytest never exiting after a failed live test)."""

    def slow(request: httpx2.Request) -> httpx2.Response:
        import time

        time.sleep(0.5)
        return reply(request, responses_body([text_output("ok")]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(mocked_router(slow), EventBus(redactor=Redactor()), workspace=workspace)
    runner = asyncio.create_task(host.run())
    await host.submit(SendMessage(text="hi"))
    await asyncio.sleep(0.2)
    runner.cancel()
    async with asyncio.timeout(10):
        with contextlib.suppress(asyncio.CancelledError):
            await runner
    assert runner.done()
