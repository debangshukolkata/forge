"""FC1 (D-629) in headless Edge: the Steps tab draws what DebCraft did for a request, from the events alone."""

# ruff: noqa: F811, RUF001  (fixtures are imported from tests.test_web_e2e; the page shows a real multiplication sign)

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from forge.protocol.events import EventBus, EventType
from forge.safety.redact import Redactor
from forge.safety.server_security import ServerSecurity
from forge.workspace.workspace import Workspace
from tests.conftest import REPO_ROOT
from tests.test_web_e2e import configured_secrets, server, workspace  # noqa: F401  (fixtures)

pytestmark = pytest.mark.e2e
playwright_api = pytest.importorskip("playwright.sync_api")

RUN = "POST http://127.0.0.1:8000/api/agents/argocd/run"


async def _call(
    bus: EventBus,
    ident: str,
    name: str,
    summary: str,
    ok: bool = True,
    preview: str = "done",
    seconds: float = 1.0,
    arguments: dict[str, Any] | None = None,
) -> None:
    await bus.publish(
        EventType.TOOL_CALL_STARTED,
        {"id": ident, "name": name, "summary": summary, "arguments": arguments or {}},
    )
    await bus.publish(
        EventType.TOOL_CALL_FINISHED,
        {"id": ident, "name": name, "ok": ok, "summary": summary, "preview": preview, "duration_s": seconds},
    )


async def _script(workspace: Workspace) -> None:
    bus = EventBus(workspace.forge_dir / "transcripts" / "events.jsonl", redactor=Redactor())
    await bus.publish(EventType.USER_MESSAGE, {"text": "What does the billing agent do?"})
    await _call(bus, "a1", "grep", "billing")
    await bus.publish(EventType.MESSAGE_DONE, {"text": "It lists invoices."})
    await bus.publish(
        EventType.USER_MESSAGE,
        {"text": "Run the following prompt in the Argo CD agent - Show all available Deployments"},
    )
    await _call(
        bus, "s1", "load_skill", "load_skill", arguments={"name": "solve-against-running-system"}, seconds=2
    )
    await _call(bus, "l1", "code_map", "code_map endpoints", seconds=12)
    await _call(bus, "l2", "code_map", "code_map find argocd", seconds=9)
    await _call(bus, "l3", "read_file", "controllers/agents.py", seconds=10)
    await _call(bus, "l4", "grep", "def run_agent", seconds=10)
    await _call(
        bus,
        "b1",
        "start_background",
        "start the application",
        ok=False,
        preview="port 8000 is busy",
        seconds=6,
    )
    await _call(bus, "b2", "start_background", "start the application", seconds=12)
    await _call(
        bus,
        "h1",
        "http_request",
        RUN,
        preview="HTTP 200\nThe endpoint asked for a token, so DebCraft signed in to dev and sent DEV_TOKEN itself.",
        seconds=74,
    )
    await _call(
        bus, "h2", "http_request", "GET http://127.0.0.1:8000/api/health", preview="HTTP 503", seconds=1
    )
    await bus.publish(
        EventType.MESSAGE_DONE,
        {"text": "The Argo CD agent lists 12 deployments: payments-api, search-worker"},
    )


def test_the_steps_tab_shows_each_step_with_its_failures_and_goes_to_the_chat(
    server: ServerSecurity, workspace: Workspace
) -> None:
    asyncio.run(_script(workspace))
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        problems: list[str] = []
        page.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Start something new.")
        page.evaluate(
            "p => fetch('/api/open', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({workspace: p})})",
            str(workspace.root),
        )
        page.reload()
        page.click("[role=tab][title=Steps]")
        page.wait_for_selector("[data-testid=steps] [data-step=answer]")
        requests = page.locator("[data-testid=steps-request]")
        assert requests.count() == 2
        latest = requests.nth(0)  # the request in hand is on top and open; the earlier one is folded
        text = latest.inner_text()
        kinds = latest.locator("[data-step]").evaluate_all("all => all.map(e => e.dataset.step)")
        assert kinds == ["skill", "look", "start", "call", "call", "answer"], kinds
        assert "Loaded the skill solve-against-running-system" in text
        assert "Looked through the code" in text and "code_map ×2, read_file, grep" in text and "41 s" in text
        assert "✕ port 8000 is busy" in text and "then worked" in text
        assert "Called POST /api/agents/argocd/run" in text and "401 → signed in to dev" in text
        assert "✕ HTTP 503" in text and "not solved" in text
        assert "Answer: The Argo CD agent lists 12 deployments" in text
        assert "6 steps" not in text and "5 steps, 2 failed" in text
        assert requests.nth(1).locator("[data-step]").count() == 0
        page.screenshot(path=str(shots / "steps-tab-light.png"))
        requests.nth(1).locator("button").first.click()
        assert requests.nth(1).locator("[data-step]").count() == 2  # one step and its answer
        latest.locator("button:has-text('Started the application')").click()  # goes to that call in the chat
        page.wait_for_selector(".jump-flash")
        browser.close()
    assert not problems, problems
