"""The Run map and the live activity line in headless Edge (D-119, D-133), driven by live events published
into a real session. They replace the two tests that were skipped under D-131."""

from __future__ import annotations

import pytest

from forge.protocol.events import EventType
from forge.workflow.state import Task
from forge.workspace.workspace import Workspace
from tests.conftest import REPO_ROOT
from tests.test_web_e2e import (  # noqa: F401  (the fixtures are used by name)
    LiveServer,
    configured_secrets,
    live_server,
    open_in_edge,
    playwright_api,
    workspace,
)

pytestmark = pytest.mark.e2e

TASKS = [
    {"id": "T1", "title": "Masking function", "status": "done", "attempts": 2},
    {
        "id": "T2",
        "title": "Separators kept",
        "status": "blocked",
        "depends_on": ["T1"],
        "blocked_reason": "needs the card format from you",
    },
    {"id": "T3", "title": "Audit call without the PAN", "status": "in_progress", "depends_on": ["T1"]},
    {"id": "T4", "title": "Validation errors", "status": "pending", "depends_on": ["T2", "T3"]},
    {"id": "FIX1", "title": "Mask the PAN in the log line", "status": "pending"},
]


def test_run_map_grows_from_the_events(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    publish = live_server.publish
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        browser, page = open_in_edge(p, live_server, workspace)
        assert live_server.manager.host is not None and live_server.manager.host.orchestrator is not None
        state = live_server.manager.host.orchestrator.state

        def at(task: str | None) -> None:  # events are stamped with the task that is current
            state.current_task = task

        at(None)
        publish(EventType.USER_MESSAGE, {"text": "Mask card numbers in the audit log"})
        publish(
            EventType.QUESTION_ASKED,
            {"id": "Q1", "question": "Keep the last four digits?", "options": [{"label": "Yes"}]},
        )
        state.tasks = [Task.model_validate(t) for t in TASKS]
        publish(EventType.TASK_LIST_UPDATED, {"phase": "plan", "current_task": None, "tasks": TASKS})
        at("T1")
        publish(
            EventType.TOOL_CALL_STARTED,
            {"id": "c1", "name": "run_tests", "summary": "run tests tests/test_mask.py"},
        )
        publish(
            EventType.TOOL_CALL_FINISHED,
            {
                "id": "c1",
                "name": "run_tests",
                "ok": False,
                "summary": "run tests",
                "preview": "collected 9 items\n"
                + "\n".join(f"line {n}" for n in range(12))
                + "\nE   AssertionError: '4111********1111' != '4111 **** **** 1111'\n1 failed, 8 passed",
            },
        )
        publish(
            EventType.TOOL_CALL_STARTED, {"id": "c2", "name": "run_tests", "summary": "run tests"}
        )  # fixes it
        publish(
            EventType.TOOL_CALL_FINISHED,
            {"id": "c2", "name": "run_tests", "ok": True, "summary": "run tests", "preview": "9 passed"},
        )
        publish(
            EventType.AGENT_STARTED,
            {"id": "agent-1", "role": "debugger", "purpose": "Diagnose a failure: test_mask"},
        )
        publish(
            EventType.AGENT_FINISHED,
            {
                "id": "agent-1",
                "role": "debugger",
                "ok": True,
                "tool_calls": 4,
                "failed_calls": 0,
                "duration_s": 12.0,
                "cost_usd": 0.0123,
            },
        )
        at("T2")
        publish(EventType.NOTICE, {"kind": "stuck", "text": "The same edit failed three times."})
        publish(EventType.TOOL_CALL_STARTED, {"id": "c3", "name": "edit_file", "summary": "edit src/mask.py"})
        publish(
            EventType.TOOL_CALL_FINISHED,
            {
                "id": "c3",
                "name": "edit_file",
                "ok": False,
                "summary": "edit",
                "preview": "The user declined this action.",
            },
        )
        at("T3")
        publish(EventType.STATUS_CHANGED, {"state": "working"})
        publish(
            EventType.AGENT_STARTED,
            {"id": "agent-2", "role": "helper", "purpose": "Helper task: find the audit call"},
        )
        publish(EventType.TASK_LIST_UPDATED, {"phase": "execute", "current_task": "T3", "tasks": TASKS})
        publish(
            EventType.APPROVAL_REQUESTED,
            {"id": "A7", "title": "Approve the audit change", "body": "…", "options": ["approve", "reject"]},
        )

        # A pending question opens as a pop-up (D-214); these tests are about the run map, so set it aside.
        page.locator("[role=dialog][aria-label='Question from Forge']").wait_for(timeout=5000)
        page.click("button[aria-label='Answer later']")
        page.click("[role=tab]:has-text('Run map')")
        page.wait_for_selector("[data-testid=run-map]")
        page.wait_for_selector("[data-task=T1][data-status=done]")
        assert page.locator("[data-task]").count() == 5
        page.wait_for_selector("[data-task=T2] >> text=Blocked: needs the card format from you")
        # Nodes appear only once they have happened: Start is there, Deliver is not (nothing exported yet).
        assert (
            page.locator("[data-step=start]").count() == 1
            and page.locator("[data-step=deliver]").count() == 0
        )
        # Helper agents hang off the task that was current when they started.
        page.wait_for_selector("[data-agent=debugger][data-status=done]")
        assert "$0.0123" in page.locator("[data-agent=debugger]").inner_text()  # what the agent cost
        page.wait_for_selector("[data-agent=helper][data-status=active]")
        # Markers moved onto the nodes (D-133): failed calls, stuck warnings and helper agents per task.
        assert page.locator("[data-task=T1] [title='Failed tool calls']").inner_text().strip() == "1"
        assert page.locator("[data-task=T1] [title='Helper agents']").inner_text().strip() == "1"
        assert page.locator("[data-task=T2] [title='Stuck warnings']").inner_text().strip() == "1"
        assert page.locator("[data-task=T2] [title='Failed tool calls']").inner_text().strip() == "1"
        # The summary strip counts the same things, and says Forge is waiting for you.
        summary = page.locator("[data-testid=run-map]").inner_text()
        assert "1/5 tasks done" in summary and "1 blocked" in summary and "2 failed calls" in summary
        page.wait_for_selector("[data-testid=run-map-waiting]")
        page.wait_for_timeout(700)  # the nodes glide into place
        page.screenshot(path=str(shots / "run-map-light.png"))

        # The failures drawer: T1's failed run was fixed later, T2's was a declined edit and is still open.
        page.click("[data-task=T1] [title='Failed tool calls']")
        drawer = page.locator("[data-testid=failure-drawer]")
        drawer.wait_for()
        assert drawer.locator("[data-outcome=fixed]").count() == 1
        page.screenshot(path=str(shots / "run-map-failures-light.png"))
        page.keyboard.press("Escape")
        drawer.wait_for(state="detached")

        page.click("button[aria-label='Dark theme']")
        page.wait_for_timeout(700)
        page.screenshot(path=str(shots / "run-map-dark.png"))
        page.click("button[aria-label='Light theme']")

        # Deliver appears once the run has exported.
        publish(
            EventType.TASK_LIST_UPDATED,
            {"phase": "execute", "current_task": "T3", "tasks": TASKS, "exported": True},
        )
        page.wait_for_selector("[data-step=deliver]")

        # A task opens its place in the chat.
        page.click("[data-task=T3]")
        page.wait_for_selector("textarea[aria-label=Message]")
        problems = page.problems  # type: ignore[attr-defined]
        browser.close()
    assert not problems, problems


def test_activity_line_and_run_totals(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    """Live events (not a replay) drive the activity line, the task badge and the run totals (D-133)."""
    publish = live_server.publish
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        browser, page = open_in_edge(p, live_server, workspace)
        assert live_server.manager.host is not None and live_server.manager.host.orchestrator is not None
        state = live_server.manager.host.orchestrator.state
        tasks = [
            {"id": "T1", "title": "Masking function", "status": "done"},
            {"id": "T3", "title": "Audit call without the PAN", "status": "in_progress"},
        ]
        state.current_task = "T3"
        state.tasks = [Task(id=t["id"], title=t["title"], status=t["status"]) for t in tasks]
        # A task-list update makes the page re-read /api/state, which says "not busy" for this fake run:
        # let that settle first, then mark the run as working.
        publish(EventType.TASK_LIST_UPDATED, {"phase": "execute", "current_task": "T3", "tasks": tasks})
        page.wait_for_timeout(600)
        publish(EventType.STATUS_CHANGED, {"state": "working"})
        status = page.locator("[role=status]")
        status.first.wait_for()
        publish(
            EventType.TOOL_CALL_STARTED,
            {"id": "t1", "name": "run_tests", "summary": "run tests tests/test_masking.py"},
        )
        page.wait_for_selector("[role=status]:has-text('Running tests')")
        assert "tests/test_masking.py" in status.first.inner_text()
        publish(
            EventType.TOOL_CALL_FINISHED,
            {"id": "t1", "name": "run_tests", "ok": True, "summary": "run tests", "duration_s": 3.1},
        )
        publish(
            EventType.QUESTION_ASKED,
            {"id": "Q9", "question": "Keep the BIN?", "options": [{"label": "No"}], "recommended": "No"},
        )
        page.wait_for_selector("[role=status]:has-text('Waiting for your answer')")
        page.locator("[role=dialog][aria-label='Question from Forge']").wait_for(timeout=5000)
        page.click("button[aria-label='Answer later']")  # the pop-up (D-214) would cover the page
        # The cost counts up to each new total, then settles on the exact value.
        publish(EventType.COST_UPDATED, {"total_usd": 0.5578, "budget_usd": 5.0, "calls": 52})
        page.wait_for_selector("span[title^='Estimated cost'] >> text=$0.5578", timeout=5000)
        bucket = lambda i, o, c, n: {"input_tokens": i, "output_tokens": o, "cost_usd": c, "calls": n}  # noqa: E731
        summary = {
            "total_usd": 0.5578,
            "budget_usd": 5.0,
            "calls": 52,
            "project": {
                "total": bucket(402_000, 55_000, 0.5578, 52),
                "by_phase": {"execute": bucket(310_000, 41_000, 0.34, 30)},
                "by_task": {"T1": bucket(40_000, 5_000, 0.04, 6), "T3": bucket(700_000, 60_000, 0.61, 12)},
            },
        }
        publish(EventType.NOTICE, {"kind": "usage", "summary": summary, "cost_usd": 0.01})
        # The strip for the whole run, and the badge for the current task, over the message box.
        page.wait_for_selector("text=Run total")
        page.wait_for_selector("[title='Cost and time on the current task']")
        publish(
            EventType.MESSAGE_DONE,
            {
                "text": "T3 is done.",
                "usage": {"input_tokens": 12_400, "output_tokens": 1_100},
                "cost_usd": 0.0138,
            },
        )
        page.wait_for_selector("text=13.5k tok · $0.0138")  # the reply's own usage
        page.wait_for_timeout(1200)
        page.screenshot(path=str(shots / "activity-light.png"))
        # Per-task usage in the Tasks tab, colour-coded by the config limits (D-118).
        page.click("[role=tab]:has-text('Tasks')")
        t3 = page.locator("[role=tabpanel] li:has-text('Audit call without the PAN')")
        assert "760k tok" in t3.inner_text()
        assert (
            t3.locator("[aria-label='red usage']").count() == 1
        )  # 0.61 USD / 760k tokens: over the task limits
        assert (
            page.locator("[role=tabpanel] li:has-text('Masking function') [aria-label='green usage']").count()
            == 1
        )
        publish(EventType.STATUS_CHANGED, {"state": "idle"})
        page.wait_for_selector("[role=status]", state="detached")
        problems = page.problems  # type: ignore[attr-defined]
        browser.close()
    assert not problems, problems
