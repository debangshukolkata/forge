"""M8: stuck detection and escalation, and the reviewer's report parsing (no model involved)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from forge.agent.escalation import BLOCK, KEEP_TRYING
from forge.agent.review import parse_review
from forge.agent.state import Task
from forge.agent.stuck import StuckDetector, StuckSignal
from forge.engine.events import EventBus, EventType
from forge.engine.inputs import Answer
from forge.engine.session_host import SessionHost
from forge.llm.base import Message
from forge.safety.redact import Redactor
from forge.tools.registry import ToolRegistry
from forge.workspace.create import create_workspace
from tests.helpers import mocked_router


def test_the_same_call_three_times_without_a_change_is_stuck() -> None:
    detector = StuckDetector()
    signals = [detector.observe("run_tests", {"selector": "tests/x.py"}, ok=True) for _ in range(3)]
    assert signals[:2] == [None, None]
    assert signals[2] is not None and signals[2].kind == "repeat_call"


def test_re_running_after_an_edit_is_progress_not_repetition() -> None:
    detector = StuckDetector()
    for version in range(4):
        detector.observe(
            "edit_file",
            {"path": "a.py", "v": version},
            ok=True,
            file_path="a.py",
            file_content_hash=f"h{version}",
        )
        assert detector.observe("run_tests", {"selector": ""}, ok=True, tests_passed=True) is None


def test_the_same_error_three_times_is_stuck_even_with_edits() -> None:
    detector = StuckDetector()
    results = []
    for version in range(3):
        detector.observe(
            "edit_file", {"v": version}, ok=True, file_path="a.py", file_content_hash=f"h{version}"
        )
        results.append(
            detector.observe("verify", {"full": False}, ok=False, error_signature="KeyError: 'id'")
        )
    assert results[-1] is not None and results[-1].kind == "repeat_error"


def test_edit_revert_oscillation() -> None:
    detector = StuckDetector()
    signal = None
    for content in ["A", "B", "A", "B", "A"]:
        signal = (
            detector.observe(
                "write_file", {"c": content}, ok=True, file_path="a.py", file_content_hash=content
            )
            or signal
        )
    assert signal is not None and signal.kind == "oscillation"


def test_no_progress_and_too_many_fix_attempts() -> None:
    idle = StuckDetector(no_progress_steps=10)
    kinds = [s.kind for i in range(10) if (s := idle.observe("read_file", {"path": f"f{i}.py"}, ok=True))]
    assert kinds == ["no_progress"]

    fixing = StuckDetector(max_fix_attempts=5)
    kinds = [
        s.kind
        for i in range(6)
        if (s := fixing.observe("run_tests", {"i": i}, ok=False, error_signature=f"error {chr(65 + i)}"))
    ]
    assert kinds == ["fix_attempts"]


def test_reviewer_findings_are_parsed() -> None:
    report = """Looks mostly fine.
- [blocking] backend/claims_app/api/policies/routes.py:12 — page_size isn't bounded — cap it at 100
- [minor] backend/tests/test_policies_api.py:3 — unused import — remove it
VERDICT: changes needed"""
    findings = parse_review(report)
    assert [(f.blocking, f.text.split(":")[0]) for f in findings] == [
        (True, "backend/claims_app/api/policies/routes.py"),
        (False, "backend/tests/test_policies_api.py"),
    ]


# --- escalation levels on an orchestrated host (debugger stubbed: no model) ---


@pytest.fixture
def host(original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SessionHost:
    async def fake_debugger(router: object, context: object, problem: str) -> str:
        return "Root cause: the id key is missing. Fix: add it in service.py."

    monkeypatch.setattr("forge.agent.subagent.run_debugger", fake_debugger)
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")

    def unreachable(request: object) -> object:
        raise AssertionError("no LLM call expected")

    return SessionHost(
        mocked_router(unreachable), EventBus(redactor=Redactor()), workspace=workspace, orchestrated=True
    )


def answer_next_question(host: SessionHost, choice: str) -> asyncio.Task[None]:
    """Subscribes NOW (before the question is published), then answers it in the background."""
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)

    async def answer() -> None:
        async for event in subscription:
            if event.type == EventType.QUESTION_ASKED:
                subscription.close()
                await host.submit(Answer(question_id=event.payload["id"], choice=choice))
                return

    return asyncio.create_task(answer())


async def test_escalation_goes_reflection_debugger_user_then_block(host: SessionHost) -> None:
    assert host.agent is not None and host.orchestrator is not None
    orchestrator = host.orchestrator
    orchestrator.state.tasks = [Task(id="T1", title="service"), Task(id="T2", title="docs")]
    orchestrator._start_task(orchestrator.state.tasks[0])
    escalator, history = host.agent.escalator, [Message.user("Implement the service.")]
    signal = StuckSignal("the same error came back 3 times: KeyError", "repeat_error")

    assert await escalator.handle(signal, history) is False  # 1: reflection
    assert "stuck" in history[-1].content and "KeyError" in history[-1].content
    assert await escalator.handle(signal, history) is False  # 2: debugger (stubbed)
    assert "Root cause" in history[-1].content

    assert host.agent.tools.get("web_search") is not None
    assert await escalator.handle(signal, history) is False  # 3: look the error up on the web
    assert "web_search" in history[-1].content and "never code" in history[-1].content

    answering = answer_next_question(host, KEEP_TRYING)
    assert await escalator.handle(signal, history) is False  # 4: ask the user
    await answering
    assert KEEP_TRYING in history[-1].content

    answering = answer_next_question(host, BLOCK)
    escalator.level = 3  # the next signal asks again; this time the user says skip
    assert await escalator.handle(signal, history) is True
    await answering
    assert orchestrator.state.tasks[0].status == "blocked"
    assert "stuck" in orchestrator.state.tasks[0].blocked_reason
    assert orchestrator.state.next_task().id == "T2"  # type: ignore[union-attr]
    notices = [e.payload for e in host.bus.events_since(0) if e.payload.get("kind") == "stuck"]
    assert [n["level"] for n in notices] == [1, 2, 3, 4, 4]


async def test_too_many_fix_attempts_goes_straight_to_the_user(host: SessionHost) -> None:
    assert host.agent is not None
    answering = answer_next_question(host, KEEP_TRYING)
    stop = await host.agent.escalator.handle(StuckSignal("6 failed verification runs", "fix_attempts"), [])
    await answering
    assert stop is False and host.agent.escalator.level == 4


async def test_web_step_is_skipped_without_the_web_tools(host: SessionHost) -> None:
    assert host.agent is not None
    tools = host.agent.tools
    host.agent.tools = ToolRegistry([t for n in tools.names() if n != "web_search" and (t := tools.get(n))])
    escalator, history = host.agent.escalator, [Message.user("Implement the service.")]
    escalator.level = 2
    answering = answer_next_question(host, KEEP_TRYING)
    assert await escalator.handle(StuckSignal("same error", "repeat_error"), history) is False
    await answering
    assert escalator.level == 4
