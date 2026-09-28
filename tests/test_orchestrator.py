"""M6 orchestrator mechanics without the model: state, gates, evidence rule, questions, headless."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from forge.agent.orchestrator import Orchestrator, phase_instructions
from forge.agent.state import OrchestratorState, Phase, StateStore, Task
from forge.engine.events import Event, EventBus, EventType
from forge.engine.headless import HEADLESS_REFUSAL, auto_reply
from forge.engine.inputs import Answer, Approve, Reject
from forge.engine.session_host import SessionHost
from forge.safety.redact import Redactor
from forge.tools.interaction import OptionSpec, TaskSpec
from forge.tools.shell import is_test_command, looks_like_write
from forge.workspace.create import create_workspace
from tests.helpers import mocked_router


def unreachable(request: object) -> object:
    raise AssertionError("no LLM call expected")


@pytest.fixture
def host(original_repo: Path, tmp_path: Path) -> SessionHost:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    return SessionHost(
        mocked_router(unreachable),
        EventBus(redactor=Redactor()),
        workspace=workspace,  # type: ignore[arg-type]
        orchestrated=True,
    )


def orchestrator(host: SessionHost) -> Orchestrator:
    assert host.orchestrator is not None
    return host.orchestrator


def answer_next(host: SessionHost, reply: object) -> asyncio.Task[None]:
    """Answers the next approval/question (the UI's job). Subscribes NOW, before the request is published."""
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    return asyncio.create_task(_answer(host, reply, subscription))


async def _answer(host: SessionHost, reply: object, subscription: object) -> None:
    async for event in subscription:  # type: ignore[attr-defined]
        if event.type in (
            EventType.APPROVAL_REQUESTED,
            EventType.QUESTION_ASKED,
            EventType.USER_ACTION_REQUESTED,
        ):
            request_id = event.payload["id"]
            answer = reply(request_id) if callable(reply) else reply
            subscription.close()  # type: ignore[attr-defined]
            await host.submit(answer)
            return


# --- state ---


def test_tasks_follow_dependencies() -> None:
    state = OrchestratorState(
        tasks=[
            Task(id="T1", title="repository"),
            Task(id="T2", title="service", depends_on=["T1"]),
            Task(id="T3", title="docs"),
        ]
    )
    assert state.next_task().id == "T1"  # type: ignore[union-attr]
    state.tasks[0].status = "blocked"
    assert state.next_task().id == "T3"  # type: ignore[union-attr]  # T2 waits for T1
    assert "[!] T1 repository" in state.task_board()


def test_state_survives_a_restart(host: SessionHost) -> None:
    store = StateStore(orchestrator(host).workspace)
    state = OrchestratorState(
        phase=Phase.EXECUTE,
        requirement="Export claims",
        current_task="T2",
        tasks=[Task(id="T1", title="a", status="done"), Task(id="T2", title="b", status="in_progress")],
    )
    store.save(state)

    loaded = StateStore(orchestrator(host).workspace).load()

    assert loaded.phase == Phase.EXECUTE and loaded.current_task == "T2"
    assert store.write_document("notes/explore.md", "notes").exists()  # sub-folders are created
    assert store.write_document("reports/final.md", "report").exists()
    assert (orchestrator(host).workspace.forge_dir / "tasks.json").exists()


def test_phase_instructions_have_every_section() -> None:
    sections = phase_instructions()
    assert {"clarify", "plan", "execute", "change", "restructure"} <= set(sections)
    assert "{requirement}" in sections["clarify"] and "{test_command}" in sections["execute"]


# --- gates ---


async def test_requirements_gate(host: SessionHost) -> None:
    runner = asyncio.create_task(host.run())
    orch = orchestrator(host)

    answer_next(host, lambda i: Reject(request_id=i, instruction="Add CSV headers."))
    rejected = await orch.propose_requirements("# Export\n- CSV of claims")
    answer_next(host, lambda i: Approve(request_id=i))
    approved = await orch.propose_requirements("# Export\n- CSV of claims with headers")
    runner.cancel()

    assert "The user requested changes: Add CSV headers." in rejected.content
    assert approved.content == "Requirements approved." and orch.context.end_turn
    assert (orch.workspace.forge_dir / "REQUIREMENTS.md").read_text(encoding="utf-8").startswith("# Export")
    assert "CSV of claims with headers" in (host.context_manager.pinned.get("requirement") or "")


async def test_plan_gate_creates_tasks(host: SessionHost) -> None:
    runner = asyncio.create_task(host.run())
    orch = orchestrator(host)
    answer_next(host, lambda i: Approve(request_id=i))

    result = await orch.propose_plan(
        "# Plan",
        [TaskSpec(id="T1", title="Repository function"), TaskSpec(id="T2", title="Route", depends_on=["T1"])],
    )
    runner.cancel()

    assert result.ok and [t.id for t in orch.state.tasks] == ["T1", "T2"]
    assert "[ ] T2 Route" in (host.context_manager.pinned.get("phase_and_tasks") or "")


async def test_no_claim_without_evidence(host: SessionHost) -> None:
    orch = orchestrator(host)
    orch.state.tasks = [Task(id="T1", title="Add route")]
    orch._start_task(orch.state.tasks[0])
    context = orch.context

    context.step += 1
    context.last_edit_step = context.step  # an edit, no test run after it
    refused = await orch.task_update("T1", "done", "", "looks fine", "", context)
    context.step += 1
    context.last_verified_step = context.step  # tests passed after the edit
    accepted = await orch.task_update("T1", "done", "Route added.", "pytest: 17 passed", "", context)

    assert not refused.ok and "no passing test run since your last edit" in refused.content
    assert accepted.ok and orch.state.tasks[0].status == "done"
    assert "pytest: 17 passed" in (orch.workspace.forge_dir / "PROGRESS.md").read_text(encoding="utf-8")


async def test_design_fork_is_asked_and_logged(host: SessionHost) -> None:
    runner = asyncio.create_task(host.run())
    orch = orchestrator(host)
    answer_next(host, lambda i: Answer(question_id=i, choice="New table", text="keep it small"))

    result = await orch.ask_user(
        "Where do exports live?",
        "Two options.",
        [OptionSpec(label="New table"), OptionSpec(label="New column")],
        "New table",
    )
    runner.cancel()

    assert result == "The user chose: New table. They added: keep it small"
    assert "Where do exports live? → New table" in (orch.workspace.forge_dir / "DECISIONS.md").read_text(
        encoding="utf-8"
    )
    assert "Recommended: New table" in (orch.workspace.forge_dir / "DISCUSSIONS.md").read_text(
        encoding="utf-8"
    )


async def test_user_action_done_is_verified_and_cant_asks_for_a_workaround(host: SessionHost) -> None:
    runner = asyncio.create_task(host.run())
    orch = orchestrator(host)

    answer_next(host, lambda i: Answer(question_id=i, choice="done"))
    done = await orch.request_user_action(
        "Create folder", ["mkdir x"], "Write-Output verified-ok", orch.context
    )
    answer_next(host, lambda i: Answer(question_id=i, choice="cant", text="no rights"))
    cant = await orch.request_user_action("Grant DB role", ["GRANT ..."], None, orch.context)
    runner.cancel()

    assert done.ok and "verified-ok" in done.content
    assert "can't do this (no rights)" in cant.content and "workaround" in cant.content


# --- headless and helpers ---


def event(event_type: EventType, **payload: object) -> Event:
    return Event(seq=1, type=event_type, ts="", payload={"id": "x", **payload})


def test_headless_replies() -> None:
    plan = auto_reply(event(EventType.APPROVAL_REQUESTED, kind="plan"), auto_approve=True)
    pip = auto_reply(event(EventType.APPROVAL_REQUESTED, always_ask=True), auto_approve=True)
    command = auto_reply(event(EventType.APPROVAL_REQUESTED, always_ask=False), auto_approve=True)
    question = auto_reply(
        event(EventType.QUESTION_ASKED, options=[{"label": "A"}, {"label": "B"}], recommended="B"),
        auto_approve=True,
    )
    action = auto_reply(event(EventType.USER_ACTION_REQUESTED), auto_approve=True)
    no_flag = auto_reply(event(EventType.APPROVAL_REQUESTED, kind="plan"), auto_approve=False)

    assert isinstance(plan, Approve) and isinstance(command, Approve)
    assert isinstance(pip, Reject) and pip.instruction == HEADLESS_REFUSAL  # never the always-ask list (A-9)
    assert isinstance(question, Answer) and question.choice == "B"
    assert isinstance(action, Answer) and action.choice == "cant"
    assert isinstance(no_flag, Reject)


def test_command_classification_for_evidence() -> None:
    assert is_test_command("& 'C:\\venv\\python.exe' -m pytest -q tests/test_x.py")
    assert not is_test_command("python -m ruff check .")
    assert looks_like_write("python -m ruff format .") and not looks_like_write("python -m pytest -q")


async def test_messages_after_done_start_a_change_request(host: SessionHost) -> None:
    orch = orchestrator(host)
    orch.state.phase = Phase.DONE
    orch.state.requirement = "Export claims"

    orch._start_change("Also include the policy number", restructure=False)

    assert orch.state.phase == Phase.PLAN and orch.state.change_request == "Also include the policy number"
    assert orch._plan_kind() == "change"
    assert "Change request: Also include the policy number" in orch.state.requirement


def test_a_change_plan_reusing_task_ids_still_runs_its_tasks() -> None:
    """A restructure plan with T1/T2 while T1..T6 are done used to be dropped silently (nothing ran)."""
    from forge.agent.orchestrator import _renumbered, _unique_id

    new = _renumbered(
        [Task(id="T1", title="move service"), Task(id="T2", title="update imports", depends_on=["T1"])],
        {"T1", "T2", "T3", "FIX1"},
    )
    assert [t.id for t in new] == ["CT1", "CT2"]
    assert new[1].depends_on == ["CT1"]
    assert _unique_id("FIX1", {"FIX1", "FIX2"}) == "FIX3"
    assert _unique_id("FIX1", set()) == "FIX1"
