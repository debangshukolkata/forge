"""Orchestrator mechanics without the model: state, the flat loop, evidence rule, questions, cadence,
headless (spec §7, D-128/D-130/D-132)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx2
import pytest

from forge.engine.headless import HEADLESS_REFUSAL, auto_reply
from forge.engine.session_host import SessionHost
from forge.llm.base import Message
from forge.protocol.events import Event, EventBus, EventType
from forge.protocol.inputs import Answer, Approve, Reject
from forge.safety.redact import Redactor
from forge.toolkit.shell import is_test_command, looks_like_write
from forge.tools.interaction import OptionSpec, TaskSpec
from forge.workflow.orchestrator import Orchestrator, detect_cadence, requirement_instructions
from forge.workflow.state import OrchestratorState, StateStore, Task
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
    """No phase field (D-131): what survives a restart is the task list, current task and cadence."""
    store = StateStore(orchestrator(host).workspace)
    state = OrchestratorState(
        started=True,
        requirement="Export claims",
        current_task="T2",
        cadence="free_hand",
        tasks=[Task(id="T1", title="a", status="done"), Task(id="T2", title="b", status="in_progress")],
    )
    store.save(state)

    loaded = StateStore(orchestrator(host).workspace).load()

    assert loaded.current_task == "T2" and loaded.cadence == "free_hand"
    assert store.write_document("notes/explore.md", "notes").exists()  # sub-folders are created
    assert store.write_document("reports/final.md", "report").exists()
    assert (orchestrator(host).workspace.forge_dir / "tasks.json").exists()


def test_resume_summary_is_honest_without_a_phase() -> None:
    fresh = OrchestratorState()
    assert fresh.resume_summary() == "No requirement given yet."

    mid = OrchestratorState(
        started=True,
        current_task="T2",
        cadence="ask_every_step",
        tasks=[Task(id="T1", title="a", status="done"), Task(id="T2", title="b", status="in_progress")],
    )
    summary = mid.resume_summary()
    assert "1 done" in summary and "1 pending" in summary and "T2" in summary and "ask every step" in summary


def test_requirement_instructions_have_every_section() -> None:
    sections = requirement_instructions()
    assert {"requirement", "change", "restructure"} <= set(sections)
    assert "{requirement}" in sections["requirement"] and "{test_command}" in sections["requirement"]


# --- cadence (D-130) ---


def test_detect_cadence_recognises_the_worked_example() -> None:
    assert (
        detect_cadence("go ahead with the recommended option, don't ask me, I'm going to sleep")
        == "free_hand"
    )
    assert detect_cadence("ask me before every step from now on please") == "ask_every_step"
    assert detect_cadence("please fix the login bug") is None


async def test_cadence_instruction_sets_permission_gate_and_persists(host: SessionHost) -> None:
    """Cadence detection itself doesn't need a live agent turn, so this calls set_cadence (what
    handle_message calls internally after detect_cadence) rather than running the whole loop through the
    KB check and the model — that's exercised end-to-end by the live tests."""
    orch = orchestrator(host)
    assert host.agent is not None
    assert detect_cadence("go ahead with the recommended option, don't ask me") == "free_hand"

    orch.set_cadence("free_hand")

    assert orch.state.cadence == "free_hand"
    assert host.agent.gate.mode == "auto"
    reloaded = StateStore(orch.workspace).load()
    assert reloaded.cadence == "free_hand"  # survives a reload, i.e. a restart (D-132)


# --- propose_requirements / propose_plan: optional, not gates (D-128) ---


async def test_propose_requirements_is_not_a_gate(host: SessionHost) -> None:
    """No approval round-trip: it just writes the document and returns immediately."""
    orch = orchestrator(host)

    result = await orch.propose_requirements("# Export\n- CSV of claims with headers")

    assert result.ok and "Saved REQUIREMENTS.md" in result.content
    assert (orch.workspace.forge_dir / "REQUIREMENTS.md").read_text(encoding="utf-8").startswith("# Export")
    assert "CSV of claims with headers" in (host.context_manager.pinned.get("requirement") or "")


async def test_propose_plan_sets_tasks_without_approval(host: SessionHost) -> None:
    orch = orchestrator(host)

    result = await orch.propose_plan(
        "# Plan",
        [TaskSpec(id="T1", title="Repository function"), TaskSpec(id="T2", title="Route", depends_on=["T1"])],
    )

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
    """No requirements/plan gate any more (D-128): every APPROVAL_REQUESTED is treated the same way."""
    pip = auto_reply(event(EventType.APPROVAL_REQUESTED, always_ask=True), auto_approve=True)
    command = auto_reply(event(EventType.APPROVAL_REQUESTED, always_ask=False), auto_approve=True)
    question = auto_reply(
        event(EventType.QUESTION_ASKED, options=[{"label": "A"}, {"label": "B"}], recommended="B"),
        auto_approve=True,
    )
    action = auto_reply(event(EventType.USER_ACTION_REQUESTED), auto_approve=True)
    no_flag = auto_reply(event(EventType.APPROVAL_REQUESTED, always_ask=False), auto_approve=False)

    assert isinstance(command, Approve)
    assert isinstance(pip, Reject) and pip.instruction == HEADLESS_REFUSAL  # never the always-ask list (A-9)
    assert isinstance(question, Answer) and question.choice == "B"
    assert isinstance(action, Answer) and action.choice == "cant"
    assert isinstance(no_flag, Reject)  # not auto_approve: nothing is approved either


def test_command_classification_for_evidence() -> None:
    assert is_test_command("& 'C:\\venv\\python.exe' -m pytest -q tests/test_x.py")
    assert not is_test_command("python -m ruff check .")
    assert looks_like_write("python -m ruff format .") and not looks_like_write("python -m pytest -q")


async def test_messages_after_export_start_a_change_request(host: SessionHost) -> None:
    orch = orchestrator(host)
    orch.state.started = True
    orch.state.exported = True
    orch.state.requirement = "Export claims"

    orch._start_change("Also include the policy number", restructure=False)

    assert orch.state.change_request == "Also include the policy number"
    assert orch.state.exported is False  # a new cycle starts
    assert orch._change_kind() == "change"
    assert "Change request: Also include the policy number" in orch.state.requirement


def test_a_change_plan_reusing_task_ids_still_runs_its_tasks() -> None:
    """A restructure plan with T1/T2 while T1..T6 are done used to be dropped silently (nothing ran)."""
    from forge.workflow.orchestrator import _renumbered, _unique_id

    new = _renumbered(
        [Task(id="T1", title="move service"), Task(id="T2", title="update imports", depends_on=["T1"])],
        {"T1", "T2", "T3", "FIX1"},
    )
    assert [t.id for t in new] == ["CT1", "CT2"]
    assert new[1].depends_on == ["CT1"]
    assert _unique_id("FIX1", {"FIX1", "FIX2"}) == "FIX3"
    assert _unique_id("FIX1", set()) == "FIX1"


# --- one conversation across tasks (D-162) ---


def test_the_brief_is_recognised_so_it_is_sent_once(host: SessionHost) -> None:
    orch = orchestrator(host)
    orch.state.requirement, orch.state.started = "Add an endpoint", True
    assert not orch._briefed()
    host.history.append(Message.system(orch._format("requirement")))
    assert orch._briefed()


def test_starting_the_next_task_keeps_the_conversation(host: SessionHost) -> None:
    orch = orchestrator(host)
    orch.state.requirement, orch.state.started = "Add an endpoint", True
    host.history.append(Message.system(orch._format("requirement")))
    host.history.append(Message.user("earlier exploration the model must not have to redo"))
    orch.state.tasks = [Task(id="T1", title="repository", status="done"), Task(id="T2", title="service")]
    before = list(host.history)
    orch._start_task(orch.state.tasks[1])
    assert host.history[: len(before)] == before  # nothing dropped
    assert (
        host.history[-1].role == "system"
        and "Next task" in host.history[-1].content
        and "T2" in host.history[-1].content
    )


def test_a_fresh_process_is_briefed_again_when_it_resumes(host: SessionHost) -> None:
    orch = orchestrator(host)
    orch.state.requirement, orch.state.started = "Add an endpoint", True
    orch.state.tasks = [Task(id="T1", title="repository")]
    orch._start_task(orch.state.tasks[0], resumed=True)
    assert any("Add an endpoint" in m.content for m in host.history if m.role == "user")


# --- follow-up messages reach the model (D-163) ---


@pytest.fixture
def talking_host(original_repo: Path, tmp_path: Path) -> tuple[SessionHost, list[int]]:
    """A host whose model just answers in plain text; the list counts the model calls."""
    from tests.helpers import reply, responses_body, text_output

    calls: list[int] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return reply(request, responses_body([text_output("The app is running on port 5055.")]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(
        mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace, orchestrated=True
    )
    return host, calls


async def test_a_follow_up_after_delivery_reaches_the_model_and_does_not_re_announce(
    talking_host: tuple[SessionHost, list[int]],
) -> None:
    host, calls = talking_host
    orch = orchestrator(host)
    orch.state.requirement, orch.state.started, orch.state.exported = "Add an endpoint", True, True
    orch.state.tasks = [
        Task(id="T1", title="repository", status="done"),
        Task(id="T2", title="x", status="blocked"),
    ]
    await orch.handle_message("please run the app and show me")
    assert len(calls) == 1, (
        "the model must answer the follow-up (it used to be skipped: tasks were all settled)"
    )
    assert orch.state.exported and not orch.state.change_request  # resume-safe again, nothing rebuilt
    done = [e for e in host.bus.events_since(0) if e.type == EventType.MESSAGE_DONE]
    assert any("port 5055" in str(e.payload.get("text")) for e in done)
    assert not any("task(s) completed" in str(e.payload.get("text")) for e in done)  # no repeated "Done: ..."


async def test_a_plain_text_answer_ends_the_turn_without_a_nudge(
    talking_host: tuple[SessionHost, list[int]],
) -> None:
    host, calls = talking_host
    orch = orchestrator(host)
    await orch.handle_message("Which database should the report use?")
    assert len(calls) == 1 and not orch.state.exported


async def test_a_blocked_task_can_be_marked_done_once_the_cause_is_fixed(host: SessionHost) -> None:
    from forge.toolkit.base import ToolContext

    orch = orchestrator(host)
    orch.state.tasks = [Task(id="T1", title="repository", status="blocked", blocked_reason="flask missing")]
    context = host.agent.context  # type: ignore[union-attr]
    assert isinstance(context, ToolContext)
    result = await orch.task_update(
        "T1", "done", "Installed flask; tests pass.", "pytest: 9 passed", "", context
    )
    assert result.ok and orch.state.task("T1").status == "done"  # type: ignore[union-attr]
    missing = await orch.task_update("T9", "done", "", "", "", context)
    assert not missing.ok and "No task T9" in missing.content


def test_mode_b_cwd_project_means_the_project_root(tmp_path: Path, isolated_forge_home: Path) -> None:
    from forge.modeb.profile import ProfileStore
    from forge.modeb.workspace import create_standalone_workspace

    workspace = create_standalone_workspace(tmp_path / "ws", ProfileStore(isolated_forge_home).create("demo"))
    assert workspace.path_of("project") == workspace.repo_dir
    assert workspace.path_of("./project") == workspace.repo_dir


async def test_the_follow_up_text_reaches_the_model_as_the_latest_user_turn(
    original_repo: Path, tmp_path: Path
) -> None:
    import json

    from tests.helpers import reply, responses_body, text_output

    seen: list[dict[str, object]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(request.content))
        return reply(request, responses_body([text_output("done")]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(
        mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace, orchestrated=True
    )
    orch = orchestrator(host)
    orch.state.requirement = "Build the attendance app.\n\nChange request: install flask and run the tests"
    orch.state.started = orch.state.exported = True
    orch.state.tasks = [Task(id="T1", title="app", status="done")]
    await orch.handle_message("Add a Department filter and a CSV export to the HR page.")
    items = [i for i in seen[0]["input"] if isinstance(i, dict) and i.get("role") == "user"]  # type: ignore[union-attr]
    assert "Department filter" in json.dumps(items[-1])
    assert any(
        "install flask" in json.dumps(i) for i in seen[0]["input"]
    )  # earlier context is still there  # type: ignore[union-attr]


def test_the_restructure_brief_carries_the_users_instruction(host: SessionHost) -> None:
    orch = orchestrator(host)
    orch.state.requirement, orch.state.started = "Build the app.", True
    orch._start_change("Move the service code into claims_app/services/policies_service.py", restructure=True)
    brief = host.history[-1].content
    assert "policies_service.py" in brief and "Behaviour must not change" in brief


async def test_work_without_a_task_list_is_still_delivered(
    talking_host: tuple[SessionHost, list[int]],
) -> None:
    host, _ = talking_host
    orch = orchestrator(host)
    host.agent.context.last_edit_step = 5  # type: ignore[union-attr]  # the model edited files, planned no tasks
    await orch.handle_message("Build a small tool.")
    assert orch.state.exported and not orch.state.tasks
    done = [str(e.payload.get("text")) for e in host.bus.events_since(0) if e.type == EventType.MESSAGE_DONE]
    assert any(t.startswith("Done: work finished.") for t in done), done


async def test_a_plain_question_without_edits_does_not_deliver_or_finish(
    talking_host: tuple[SessionHost, list[int]],
) -> None:
    host, _ = talking_host
    orch = orchestrator(host)
    await orch.handle_message("Which database should it use?")
    assert not orch.state.exported


async def test_a_task_that_changed_the_ui_needs_a_browser_check_before_done(host: SessionHost) -> None:
    from forge.toolkit.base import ToolContext

    orch = orchestrator(host)
    orch.state.tasks = [Task(id="T1", title="cart page")]
    orch.state.current_task = "T1"
    context = host.agent.context  # type: ignore[union-attr]
    assert isinstance(context, ToolContext)
    context.step = 7
    context.last_ui_edit_step = 7  # templates/cart.html was edited; the unit tests pass
    refused = await orch.task_update("T1", "done", "", "pytest: 9 passed", "", context)
    assert not refused.ok and "browser" in refused.content and "web-ui-verification" in refused.content
    context.step, context.last_browser_step = 9, 9  # the app was then opened and clicked through
    accepted = await orch.task_update(
        "T1", "done", "Cart works.", "browser: added two items, saw Cart (2)", "", context
    )
    assert accepted.ok


async def test_a_blocked_ui_task_does_not_need_a_browser_check(host: SessionHost) -> None:
    orch = orchestrator(host)
    orch.state.tasks = [Task(id="T1", title="cart page")]
    orch.state.current_task = "T1"
    context = host.agent.context  # type: ignore[union-attr]
    context.step = context.last_ui_edit_step = 4  # type: ignore[union-attr]
    assert (await orch.task_update("T1", "blocked", "", "", "flask missing", context)).ok  # type: ignore[arg-type]


async def test_a_ui_change_without_a_browser_check_sends_the_model_back_once(
    talking_host: tuple[SessionHost, list[int]],
) -> None:
    host, calls = talking_host
    orch = orchestrator(host)
    host.agent.context.last_edit_step = host.agent.context.last_ui_edit_step = 5  # type: ignore[union-attr]
    await orch.handle_message("Make the calendar fit on a phone.")
    assert len(calls) == 2  # the answer, then one more run after the note about the missing browser check
    assert any(
        "not used the running app in a browser" in m.content for m in host.history if m.role == "system"
    )
    assert orch.state.exported  # and then it is delivered; it is only asked once


async def test_a_ui_change_that_was_checked_in_a_browser_is_not_questioned(
    talking_host: tuple[SessionHost, list[int]],
) -> None:
    host, calls = talking_host
    orch = orchestrator(host)
    context = host.agent.context  # type: ignore[union-attr]
    context.last_edit_step = context.last_ui_edit_step = 5
    context.last_browser_step = 8
    await orch.handle_message("Make the calendar fit on a phone.")
    assert len(calls) == 1


async def test_stopping_at_the_step_cap_is_not_finishing(original_repo: Path, tmp_path: Path) -> None:
    from tests.helpers import function_call_output, reply, responses_body

    def handler(request: httpx2.Request) -> httpx2.Response:  # the model never stops calling a tool
        return reply(request, responses_body([function_call_output("list_dir", '{"path": "."}')]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(
        mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace, orchestrated=True
    )
    assert host.agent is not None
    host.agent.max_iterations = 2
    host.agent.context.last_edit_step = 5  # files changed: this would normally be delivered
    orch = orchestrator(host)
    orch.state.tasks = [Task(id="T1", title="x", status="done")]
    await orch.handle_message("Build a lot.")
    assert host.agent.hit_iteration_limit and not orch.state.exported
    done = [str(e.payload.get("text")) for e in host.bus.events_since(0) if e.type == EventType.MESSAGE_DONE]
    assert not any("Done:" in t for t in done), done  # no delivery while work is cut off


def test_the_step_cap_is_a_generous_runaway_guard() -> None:
    from tests.helpers import default_config

    assert default_config().limits.max_iterations_per_task >= 100
