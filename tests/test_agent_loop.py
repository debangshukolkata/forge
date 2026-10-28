"""Agent-loop failure handling with failures injected at the transport layer (DECISIONS D-008)."""

from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path

import httpx2

from forge.agent.hooks import HookOutcome
from forge.agent.loop import CUT_OFF_NOTE, FAILURE_HEAD_CHARS, FAILURE_TAIL_CHARS, STOP_HOOK_NOTE, _preview
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
    verifier_and_critic = await _elapsed_for(
        host, [("spawn_subagent", {"agent": "verifier"}), ("spawn_subagent", {"agent": "design-critic"})]
    )
    critic_then_verifier = await _elapsed_for(
        host, [("spawn_subagent", {"agent": "design-critic"}), ("spawn_subagent", {"agent": "verifier"})]
    )
    debugger_and_verifier = await _elapsed_for(
        host, [("spawn_subagent", {"agent": "debugger"}), ("spawn_subagent", {"agent": "verifier"})]
    )

    assert two_reads < 0.5 and two_explores < 0.5  # about the time of one
    assert two_verifiers >= 0.55  # one after the other: they write files and start the app
    assert 0.55 <= six_explores < 0.95  # capped at 4 at once: 4 together, then 2
    assert (
        verifier_and_critic < 0.5 and critic_then_verifier < 0.5
    )  # X4: the critic only looks, in either order
    assert debugger_and_verifier >= 0.55  # a debugger runs commands, so it never overlaps a verifier


async def test_a_running_subagent_reports_its_steps_to_the_session(
    original_repo: Path, tmp_path: Path
) -> None:
    from forge.subagents.subagent import run_debugger
    from tests.helpers import function_call_output

    calls = {"n": 0}

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return reply(request, responses_body([function_call_output("list_dir", '{"path": "."}')]))
        return reply(request, responses_body([text_output("Root cause: x. Fix: y.")]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    assert host.agent is not None
    report = await run_debugger(host.router, host.agent.context, "the build fails")
    assert "Root cause" in report
    steps = [e.payload for e in host.bus.events_since(0) if e.type == EventType.SUBAGENT_STEP]
    kinds = [s["kind"] for s in steps]
    assert "tool_started" in kinds and "tool_finished" in kinds
    assert all(s["agent"].startswith("agent-") for s in steps)
    finished = [e.payload for e in host.bus.events_since(0) if e.type == EventType.AGENT_FINISHED]
    assert len(finished) == 1 and finished[0]["cost_usd"] > 0  # the mocked replies carry token counts


async def test_a_ui_file_changed_again_and_again_gets_a_note_to_fix_the_cause_once(
    original_repo: Path, tmp_path: Path
) -> None:
    """D1, D-370: patching one value at a time is the pattern behind drifting pages; from the sixth change of one UI file the result carries a note."""
    from forge.agent.loop import REWORK_EDITS, REWORK_EVERY
    from forge.toolkit.base import ToolResult

    def handler(request: httpx2.Request) -> httpx2.Response:
        return reply(request, responses_body([text_output("ok")]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    loop = host.agent
    assert loop is not None
    ok = ToolResult(ok=True, content="")
    notes = [
        loop._note_ui_evidence("edit_file", {"path": "static/Style.css"}, ok)
        for _ in range(REWORK_EDITS + REWORK_EVERY)
    ]
    assert all(note is None for note in notes[: REWORK_EDITS - 1])
    assert (
        notes[REWORK_EDITS - 1]
        and "changed 6 times" in notes[REWORK_EDITS - 1]
        and "one multi_edit" in notes[REWORK_EDITS - 1]
    )
    assert all(note is None for note in notes[REWORK_EDITS : REWORK_EDITS + REWORK_EVERY - 1])
    assert notes[-1] and "changed 10 times" in notes[-1]
    assert (
        loop._note_ui_evidence("edit_file", {"path": "tests/test_page.py"}, ok) is None
    )  # tests and other files are not counted
    assert loop._note_ui_evidence("edit_file", {"path": "notes.md"}, ok) is None


async def test_plan_mode_asks_the_planner_role_and_normal_mode_the_coder(
    original_repo: Path, tmp_path: Path
) -> None:
    """D-411: read-only analysis in plan mode runs on the planner's model (the Claude Code 'plan with the stronger model' idea)."""

    def handler(request: httpx2.Request) -> httpx2.Response:
        return reply(request, responses_body([text_output("ok")]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    loop = host.agent
    assert loop is not None
    assert loop.active_role == "coder"
    loop.gate.mode = "plan"
    assert loop.active_role == "planner"
    loop.role = "reviewer"  # a subagent keeps its own role in any mode
    assert loop.active_role == "reviewer"


class _StopHooks:
    """Stands in for the hook runner: a stop hook that fails the first time it runs and passes afterwards."""

    def __init__(self) -> None:
        self.runs = 0

    def has(self, event: str) -> bool:
        return event == "stop"

    async def run(self, event: str, tool: str = "", file: str = "") -> list[HookOutcome]:
        self.runs += 1
        return [
            HookOutcome(
                "pytest -x", True, self.runs > 1, "" if self.runs > 1 else "FAILED tests/test_a.py::test_one"
            )
        ]


async def test_a_failing_stop_hook_sends_the_model_back_to_work_once_and_then_lets_it_finish(
    original_repo: Path, tmp_path: Path
) -> None:
    """C12 a (D-515): the first stop-hook run fails, so the model gets its output and answers again; the second passes and the turn ends."""
    bodies: list[dict[str, object]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        bodies.append(json.loads(request.content))
        return reply(request, responses_body([text_output("Done: the change is in.")]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    assert host.agent is not None
    hooks = _StopHooks()
    host.agent.hooks = hooks  # type: ignore[assignment]
    runner = asyncio.create_task(host.run())
    await host.submit(SendMessage(text="Change the thing."))
    for _ in range(100):
        await asyncio.sleep(0.05)
        if any(e.type == EventType.COST_UPDATED for e in host.bus.events_since(0)):
            break
    runner.cancel()

    assert hooks.runs == 2 and len(bodies) == 2
    assert any(
        m.role == "system" and str(m.content).startswith(STOP_HOOK_NOTE) and "test_one" in str(m.content)
        for m in host.history
    )
    kinds = [e.payload.get("kind") for e in host.bus.events_since(0) if e.type == EventType.NOTICE]
    assert "stop_hook" in kinds
