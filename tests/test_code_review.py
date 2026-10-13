"""C4 (D-308): the two-axis code review and its optional gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx2
import pytest

from forge.engine.session_host import SessionHost
from forge.protocol.events import EventBus
from forge.safety.redact import Redactor
from forge.subagents.code_review import AxisReport, aggregate, find_standards, run_code_review, verdict_of
from forge.subagents.review import ReviewFinding
from forge.workflow.state import Task
from forge.workspace.create import create_workspace
from forge.workspace.pyenv import PythonEnvironment
from tests.helpers import mocked_router, reply, responses_body, text_output
from tests.test_orchestrator import host as orch_host  # noqa: F401  (fixture used by name)
from tests.test_orchestrator import orchestrator


def axis(name: str, blocking: int, minor: int, report: str = "") -> AxisReport:
    findings = [ReviewFinding(True, f"a.py:{i} - broken rule {i} - fix it") for i in range(blocking)]
    findings += [ReviewFinding(False, f"b.py:{i} - smell {i} - tidy") for i in range(minor)]
    return AxisReport(name, report or "\n".join(f"- {f.render()}" for f in findings), findings)


def test_the_two_reports_stay_apart_with_counts_and_one_verdict() -> None:
    text = aggregate(
        [axis("Standards", 0, 2), axis("Spec", 1, 0, report="- [blocking] x\nVERDICT: changes needed")]
    )
    assert "## Standards" in text and "## Spec" in text
    assert text.index("## Standards") < text.index("## Spec")
    assert "Standards: 0 blocking, 2 minor" in text and "Spec: 1 blocking, 0 minor" in text
    assert text.rstrip().endswith("VERDICT: REVISE")
    assert text.count("VERDICT:") == 1  # the reviewers' own verdict lines are dropped
    assert verdict_of([axis("Standards", 0, 3), axis("Spec", 0, 0)]) == "SHIP"


def test_documented_standards_are_found_and_missing_ones_are_empty(tmp_path: Path) -> None:
    assert find_standards(tmp_path) == ""
    (tmp_path / "CONTRIBUTING.md").write_text("Use type hints everywhere.", encoding="utf-8")
    assert "Use type hints everywhere." in find_standards(tmp_path)


async def test_both_reviewers_run_with_their_own_inputs_and_blocking_findings_need_real_evidence(
    original_repo: Path, tmp_path: Path
) -> None:
    seen: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        body = request.content.decode("utf-8", errors="replace")
        seen.append(body)
        if "WHAT was ASKED" in body or "what was ASKED" in body:
            return reply(
                request,
                responses_body(
                    [
                        text_output(
                            "- [blocking] backend/helper.py:1 - returns canned value - call the service - evidence: `return 42`\nVERDICT: changes needed"
                        )
                    ]
                ),
            )
        return reply(
            request,
            responses_body([text_output("- [minor] helper.py:1 - vague name - rename\nVERDICT: pass")]),
        )

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_text("backend/helper.py", "def total():\n    return 42\n")
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    assert host.agent is not None
    text = await run_code_review(host.router, host.agent.context, "Add a total() that sums the invoices.")

    assert len(seen) == 2
    assert any(
        "Documented standards:" in b and "The request:" not in b for b in seen
    )  # the standards reviewer never sees the request
    assert any("The request:" in b and "Add a total() that sums the invoices." in b for b in seen)
    assert (
        "Spec: 1 blocking" in text
        and "Standards: 0 blocking, 1 minor" in text
        and text.rstrip().endswith("VERDICT: REVISE")
    )


async def test_without_a_request_only_the_standards_axis_runs(original_repo: Path, tmp_path: Path) -> None:
    calls: list[int] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(1)
        return reply(request, responses_body([text_output("Nothing to report.\nVERDICT: pass")]))

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_text("backend/helper.py", "X = 1\n")
    host = SessionHost(mocked_router(handler), EventBus(redactor=Redactor()), workspace=workspace)
    assert host.agent is not None
    text = await run_code_review(host.router, host.agent.context, "")
    assert len(calls) == 1 and "spec axis was skipped" in text and text.rstrip().endswith("VERDICT: SHIP")


async def test_nothing_changed_means_nothing_to_review(original_repo: Path, tmp_path: Path) -> None:
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(
        mocked_router(lambda r: reply(r, responses_body([text_output("x")]))),
        EventBus(redactor=Redactor()),
        workspace=workspace,
    )
    assert host.agent is not None
    assert "Nothing to review" in await run_code_review(host.router, host.agent.context, "anything")


async def _code_task(host: SessionHost):  # type: ignore[no-untyped-def]
    orch = orchestrator(host)
    orch.state.tasks = [Task(id="T1", title="Add helper")]
    orch._start_task(orch.state.tasks[0])
    ctx = orch.context
    orch.workspace.info.python_env = PythonEnvironment(
        python=sys.executable, venv="", app_dir=str(orch.workspace.app_dir), top_packages=[]
    )
    relative = orch.workspace.app_dir.relative_to(orch.workspace.repo_dir).as_posix() + "/review_helper.py"
    orch.workspace.write_text(relative, "def add(a: int, b: int) -> int:\n    return a + b\n")
    ctx.step += 1
    ctx.last_edit_step = ctx.step
    ctx.last_verified_step = ctx.step + 1
    ctx.step += 1
    return orch, ctx


async def test_the_review_gate_is_off_by_default(orch_host: SessionHost) -> None:  # noqa: F811
    orch, ctx = await _code_task(orch_host)
    assert (await orch.task_update("T1", "done", "Done.", "pytest passed", "", ctx)).ok


async def test_with_the_gate_on_a_task_needs_a_shipping_review_after_its_last_edit(
    orch_host: SessionHost,  # noqa: F811
) -> None:
    orch_host.router.config.review.gate = True
    orch, ctx = await _code_task(orch_host)

    first = await orch.task_update("T1", "done", "", "pytest passed", "", ctx)
    assert not first.ok and "code-review" in first.content

    ctx.step += 1
    ctx.last_review_step, ctx.review_ship = ctx.step, False  # a review ran but said REVISE
    second = await orch.task_update("T1", "done", "", "pytest passed", "", ctx)
    assert not second.ok and "REVISE" in second.content

    third = await orch.task_update(
        "T1", "done", "Done.", "pytest passed", "", ctx
    )  # two rounds, then it may close
    assert third.ok


async def test_a_shipping_review_lets_the_task_close_at_once(orch_host: SessionHost) -> None:  # noqa: F811
    orch_host.router.config.review.gate = True
    orch, ctx = await _code_task(orch_host)
    ctx.step += 1
    ctx.last_review_step, ctx.review_ship = ctx.step, True
    assert (await orch.task_update("T1", "done", "Done.", "pytest passed", "", ctx)).ok


async def test_an_edit_after_the_review_makes_it_stale(orch_host: SessionHost) -> None:  # noqa: F811
    orch_host.router.config.review.gate = True
    orch, ctx = await _code_task(orch_host)
    ctx.step += 1
    ctx.last_review_step, ctx.review_ship = ctx.step, True
    ctx.step += 1
    ctx.last_edit_step = ctx.step  # edited again after the review
    ctx.last_verified_step = ctx.step + 1
    ctx.step += 1
    refused = await orch.task_update("T1", "done", "", "pytest passed", "", ctx)
    assert not refused.ok and "code review" in refused.content


def test_the_agent_type_is_listed() -> None:
    from forge.tools.parity import BUILT_IN_TYPES

    assert "code-review" in BUILT_IN_TYPES and json.dumps(BUILT_IN_TYPES)
    _ = pytest
