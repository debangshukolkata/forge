"""X7 (D-306): which planned tasks may run in parallel, and what the scheduler tool does with the builders' results."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.tools.interaction import TaskSpec
from forge.workflow.scheduler import dependency_problems, explain, frontier, plan_batch
from forge.workflow.state import Task
from tests.test_orchestrator import host, orchestrator  # noqa: F401  (fixtures and helpers used by name)


def task(
    id: str,
    folder: str = "",
    deps: list[str] | None = None,
    resources: list[str] | None = None,
    status: str = "pending",
) -> Task:
    return Task(
        id=id,
        title=f"Task {id}",
        folder=folder,
        depends_on=deps or [],
        resources=resources or [],
        status=status,
    )  # type: ignore[arg-type]


def test_the_frontier_is_the_pending_tasks_whose_dependencies_are_done() -> None:
    tasks = [task("T1", status="done"), task("T2", deps=["T1"]), task("T3", deps=["T2"]), task("T4")]
    assert [t.id for t in frontier(tasks)] == ["T2", "T4"]


def test_independent_tasks_with_separate_folders_run_together_up_to_the_limit() -> None:
    tasks = [task(f"T{i}", folder=f"designs/{c}") for i, c in enumerate("abcd", start=1)]
    batch = plan_batch(tasks, limit=3)
    assert [t.id for t in batch.run] == ["T1", "T2", "T3"] and batch.parallel
    assert [(t.id, "limit of 3" in why) for t, why in batch.held] == [("T4", True)]


def test_overlapping_folders_and_shared_resources_keep_tasks_apart() -> None:
    tasks = [
        task("T1", folder="app"),
        task("T2", folder="app/api"),  # inside T1's folder
        task("T3", folder="web", resources=["port-5000"]),
        task("T4", folder="docs", resources=["port-5000"]),  # the same exclusive port as T3
        task("T5", folder="svc"),
    ]
    batch = plan_batch(tasks, limit=5)
    assert [t.id for t in batch.run] == ["T1", "T3", "T5"]
    reasons = {t.id: why for t, why in batch.held}
    assert "overlaps T1" in reasons["T2"] and "shares port-5000 with T3" in reasons["T4"]


def test_a_task_without_a_folder_never_runs_in_parallel() -> None:
    batch = plan_batch([task("T1"), task("T2", folder="b")], limit=3)
    assert [t.id for t in batch.run] == ["T2"] and not batch.parallel
    assert "no folder" in batch.held[0][1]


def test_unknown_dependencies_and_cycles_make_tasks_serial_and_are_explained() -> None:
    tasks = [
        task("T1", deps=["T9"], folder="a"),
        task("T2", deps=["T3"], folder="b"),
        task("T3", deps=["T2"], folder="c"),
        task("T4", folder="d"),
    ]
    problems = dependency_problems(tasks)
    assert (
        "unknown task T9" in problems["T1"]
        and "cycle" in problems["T2"]
        and "cycle" in problems["T3"]
        and "T4" not in problems
    )
    assert [t.id for t in frontier(tasks)] == ["T4"]
    assert "T2" in explain(tasks, plan_batch(tasks, 3), 3)


def test_the_explanation_names_the_off_switch_and_the_waiting() -> None:
    assert "switched off" in explain([task("T1", folder="a")], plan_batch([task("T1", folder="a")], 1), 1)
    waiting = [task("T1", folder="a", status="in_progress"), task("T2", deps=["T1"], folder="b")]
    assert "No task is ready" in explain(waiting, plan_batch(waiting, 3), 3)


def test_a_chosen_subset_limits_the_batch() -> None:
    tasks = [task("T1", folder="a"), task("T2", folder="b"), task("T3", folder="c")]
    assert [t.id for t in plan_batch(tasks, 3, only={"T1", "T3"}).run] == ["T1", "T3"]


async def test_the_plan_keeps_folders_and_resources(host) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    orch = orchestrator(host)
    await orch.propose_plan(
        "# Plan",
        [TaskSpec(id="T1", title="A", folder="designs/a", resources=["port"]), TaskSpec(id="T2", title="B")],
    )
    assert orch.state.tasks[0].folder == "designs/a" and orch.state.tasks[0].resources == ["port"]
    assert orch.state.tasks[1].folder == ""


async def test_run_ready_tasks_builds_in_parallel_records_statuses_and_sets_the_verification_gates(
    host,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # type: ignore[no-untyped-def]
    import asyncio
    import time

    from forge.workflow import orchestrator as module

    orch = orchestrator(host)
    await orch.propose_plan(
        "# Plan",
        [
            TaskSpec(id="T1", title="Design A", folder="designs/a"),
            TaskSpec(id="T2", title="Design B", folder="designs/b"),
            TaskSpec(id="T3", title="Compare", depends_on=["T1", "T2"], folder="compare"),
        ],
    )
    briefs: dict[str, str] = {}

    async def fake_builder(context: object, *, folder: str, name: str, task: str) -> tuple[str, str, str]:
        briefs[name] = task
        await asyncio.sleep(0.4)
        orch.workspace.write_text(f"{folder}/index.html", "<h1>x</h1>")
        status = "BLOCKED" if name == "t2" else "DONE"
        return (
            status,
            f"Built {name}.\nSTATUS: {status} - summary of {name}",
            f".forge/builders/{name}-report.md",
        )

    monkeypatch.setattr(module, "run_builder", fake_builder)
    orch.context.step = 10
    started = time.perf_counter()
    result = await orch.run_ready_tasks([], {"T1": "Use the blue palette."})
    elapsed = time.perf_counter() - started

    assert result.ok and elapsed < 0.7  # two builders of 0.4 s ran together
    assert (
        "[builder t1 in designs/a: DONE]" in result.content
        and "[builder t2 in designs/b: BLOCKED]" in result.content
    )
    assert (
        "Use the blue palette." in briefs["t1"]
        and "Your task T1: Design A" in briefs["t1"]
        and "Use the blue palette." not in briefs["t2"]
    )
    by_id = {t.id: t for t in orch.state.tasks}
    assert (
        by_id["T1"].status == "in_progress" and by_id["T1"].attempts == 1
    )  # the main agent still has to verify and finish it
    assert by_id["T2"].status == "blocked" and "builder BLOCKED" in by_id["T2"].blocked_reason
    assert by_id["T3"].status == "pending"  # waits for T1 and T2
    assert (
        orch.context.last_edit_step == 10 and orch.context.last_ui_edit_step == 10
    )  # html written: browser evidence is required too
    assert "Next: verify each piece" in result.content


async def test_run_ready_tasks_says_why_when_nothing_can_run_together(host) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    orch = orchestrator(host)
    await orch.propose_plan(
        "# Plan", [TaskSpec(id="T1", title="Only task", folder="a"), TaskSpec(id="T2", title="No folder")]
    )
    result = await orch.run_ready_tasks([], {})
    assert (
        result.ok and "Only 1 task(s) can start now" in result.content and "T2 Task" in result.content
    ) or "no folder" in result.content
    assert all(t.status == "pending" for t in orch.state.tasks)  # nothing was started
    host.router.config.limits.max_parallel_builders = 1
    assert "switched off" in (await orch.run_ready_tasks([], {})).content


def test_the_tool_is_offered_to_the_model_next_to_the_plan_tools(host) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    tools = orchestrator(host)._tools()
    assert all(tools.get(name) is not None for name in ("propose_plan", "run_ready_tasks", "task_update"))


@pytest.fixture(autouse=True)
def _tmp(tmp_path: Path) -> Path:
    return tmp_path
