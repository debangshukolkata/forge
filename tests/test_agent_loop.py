"""Agent-loop failure handling with failures injected at the transport layer (DECISIONS D-008)."""

from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path

import httpx2

from forge.agent.loop import CUT_OFF_NOTE, FAILURE_HEAD_CHARS, FAILURE_TAIL_CHARS, _preview
from forge.engine.session_host import SessionHost
from forge.protocol.events import EventBus, EventType
from forge.protocol.inputs import SendMessage
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
    assert bodies[0]["reasoning"]["effort"] == "medium"  # type: ignore[index]
    assert bodies[1]["reasoning"]["effort"] == "low"  # type: ignore[index]  # think less so the answer fits
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


def test_failure_preview_keeps_the_end_where_the_error_is() -> None:
    # The Run map's failures drawer (D-122) shows the error, which test runners print last.
    output = "collected 9 items\n" + "." * 5000 + "\nE   AssertionError: 12.35 != 12.36\n1 failed, 8 passed"
    preview = _preview(output, ok=False)
    assert preview.startswith("collected 9 items")
    assert preview.endswith("1 failed, 8 passed") and "AssertionError: 12.35 != 12.36" in preview
    assert len(preview) <= FAILURE_HEAD_CHARS + FAILURE_TAIL_CHARS + 3
    assert _preview("short failure", ok=False) == "short failure"
    assert _preview(output, ok=True) == output[:1500]


def test_a_subagent_that_ends_in_tool_calls_is_asked_for_a_report() -> None:
    from forge.llm.base import Message, ToolCall
    from forge.subagents.subagent import _ended_with_text, _last_text

    done = [Message.system("p"), Message.user("t"), Message(role="assistant", content="All checks passed.")]
    assert _ended_with_text(done) and _last_text(done) == "All checks passed."
    cut_off = [
        *done[:2],
        Message(
            role="assistant",
            content="",
            tool_calls=[ToolCall(id="c1", name="read_file", raw_arguments="{}", arguments={})],
        ),
        Message.tool_result("c1", "contents"),
    ]
    assert not _ended_with_text(cut_off) and _last_text(cut_off) == ""


# --- parallel tool calls and subagents (D-175) ---


def _timed_tools(log: list[tuple[str, float, float]]):  # type: ignore[no-untyped-def]
    import time

    from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

    class Pause(Tool):
        name = "slow_read"
        read_only = True
        description = "sleeps"

        class Args(ToolArgs):
            tag: str = ""

        async def run(self, args: Pause.Args, context: ToolContext) -> ToolResult:
            started = time.perf_counter()
            await asyncio.sleep(0.3)
            log.append((args.tag, started, time.perf_counter()))
            return ToolResult(ok=True, content="done")

    class Spawn(Pause):
        name = "spawn_subagent"

        class Args(ToolArgs):
            agent: str
            task: str = ""

        async def run(self, args: Spawn.Args, context: ToolContext) -> ToolResult:  # type: ignore[override]
            started = time.perf_counter()
            await asyncio.sleep(0.3)
            log.append((args.agent, started, time.perf_counter()))
            return ToolResult(ok=True, content="report")

    return Pause(), Spawn()


async def _elapsed_for(host, calls) -> float:  # type: ignore[no-untyped-def]
    import time

    from forge.llm.base import ToolCall

    results: dict = {}
    wrapped = [
        ToolCall(id=f"c{i}", name=n, raw_arguments=json.dumps(a), arguments=a)
        for i, (n, a) in enumerate(calls)
    ]
    started = time.perf_counter()
    await host.agent._run_calls(wrapped, results)
    assert len(results) == len(calls)
    return time.perf_counter() - started


async def test_read_only_agents_run_side_by_side_but_verifiers_are_serialised(
    original_repo: Path, tmp_path: Path
) -> None:
    from forge.tools.registry import ToolRegistry
    from tests.helpers import mocked_router

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(
        mocked_router(lambda request: httpx2.Response(500)),
        EventBus(redactor=Redactor()),
        workspace=workspace,
    )
    assert host.agent is not None
    log: list[tuple[str, float, float]] = []
    host.agent.tools = ToolRegistry(list(_timed_tools(log)))

    await _elapsed_for(
        host, [("slow_read", {"tag": "warm-up"})]
    )  # the first call pays one-time start-up costs
    two_reads = await _elapsed_for(host, [("slow_read", {"tag": "a"}), ("slow_read", {"tag": "b"})])
    two_explores = await _elapsed_for(host, [("spawn_subagent", {"agent": "explore"})] * 2)
    two_verifiers = await _elapsed_for(host, [("spawn_subagent", {"agent": "verifier"})] * 2)
    six_explores = await _elapsed_for(host, [("spawn_subagent", {"agent": "explore"})] * 6)

    assert two_reads < 0.5 and two_explores < 0.5  # about the time of one
    assert two_verifiers >= 0.55  # one after the other: they write files and start the app
    assert 0.55 <= six_explores < 0.95  # capped at 4 at once: 4 together, then 2
