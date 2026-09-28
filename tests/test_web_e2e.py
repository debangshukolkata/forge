"""Web UI end-to-end in headless Edge (spec §15A.6) against a real uvicorn server — the UI mechanics that don't
need the model: token login, opening a workspace, slash commands, panels, diff view, reload replay, output.zip
download, Stop, and no JavaScript/CSP errors. The model-driven run through the web UI is in
test_live_web_react.py."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

from forge.engine.events import EventBus
from forge.engine.session_host import SessionHost
from forge.safety.redact import Redactor
from forge.web.manager import WebSessionManager
from forge.web.run import free_port
from forge.web.security import ServerSecurity
from forge.web.server import create_app
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace
from tests.conftest import REPO_ROOT
from tests.helpers import mocked_router

pytestmark = pytest.mark.e2e
playwright_api = pytest.importorskip("playwright.sync_api")


def unreachable(request: object) -> object:
    raise AssertionError("no LLM call expected")


@pytest.fixture
def workspace(original_repo: Path, tmp_path: Path) -> Workspace:
    ws = create_workspace(original_repo, tmp_path / "ws", "backend")
    errors = ws.path_of("backend/claims_app/errors.py")
    errors.write_text(errors.read_text(encoding="utf-8") + "\n# edited for the e2e test\n", encoding="utf-8")
    return ws


@pytest.fixture
def server(isolated_forge_home: Path) -> Iterator[ServerSecurity]:
    port = free_port(8790)
    security = ServerSecurity(port=port)
    manager = WebSessionManager(
        isolated_forge_home,
        lambda ws: SessionHost(
            mocked_router(unreachable),
            EventBus(ws.forge_dir / "transcripts" / "events.jsonl", redactor=Redactor()),
            workspace=ws,
        ),
    )
    config = uvicorn.Config(
        create_app(manager, security),
        host="127.0.0.1",
        port=port,
        log_level="warning",
        ws="websockets-sansio",
    )
    uv = uvicorn.Server(config)
    thread = threading.Thread(target=uv.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not uv.started and time.monotonic() < deadline:
        time.sleep(0.05)
    yield security
    uv.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
def page(server: ServerSecurity) -> Iterator[object]:
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        context = browser.new_context(accept_downloads=True)
        tab = context.new_page()
        problems: list[str] = []
        tab.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
        tab.on("pageerror", lambda e: problems.append(str(e)))
        tab.problems = problems  # type: ignore[attr-defined]
        yield tab
        browser.close()


def test_web_ui_mechanics_in_edge(page, server: ServerSecurity, workspace: Workspace) -> None:  # type: ignore[no-untyped-def]
    page.goto(server.url())
    assert page.url.rstrip("/").endswith(str(server.port)), "the token must leave the URL"
    page.wait_for_selector("text=Start a project")
    page.wait_for_selector("text=Environment check")

    # Open the workspace through the API the home screen uses, then load it like a user would.
    page.evaluate(
        "p => fetch('/api/open', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({workspace: p})})",
        str(workspace.root),
    )
    page.reload()
    box = page.locator("textarea[aria-label=Message]")
    box.fill("/help")
    page.keyboard.press("Enter")
    page.wait_for_selector("pre:has-text('/rewind')")

    page.click("[role=tab]:has-text('Files')")
    page.wait_for_selector("[role=tabpanel] button:has-text('backend')")
    page.click("[role=tab]:has-text('Diffs')")
    page.wait_for_selector(".d2h-wrapper")
    assert "edited for the e2e test" in page.inner_text("[role=tabpanel]")
    page.click("[role=tab]:has-text('Learning')")
    page.wait_for_selector("[role=tabpanel] h3:has-text('Lessons')")
    page.click("[role=tab]:has-text('Settings')")
    page.wait_for_selector("[role=tabpanel] select")

    page.reload()  # state is replayed from the event log
    page.wait_for_selector("pre:has-text('/rewind')")

    with page.expect_download() as download:
        page.click("[role=tab]:has-text('Files')")
        page.click("text=Download output")
    assert download.value.suggested_filename.endswith("-output.zip")
    time.sleep(0.5)
    assert page.problems == [], page.problems  # type: ignore[attr-defined]


def test_new_project_form_in_edge(page, server: ServerSecurity, tmp_path: Path, original_repo: Path) -> None:  # type: ignore[no-untyped-def]
    # The start form: project name + folder (both modes); the repository field appears only in Mode A.
    page.goto(server.url())
    page.wait_for_selector("text=Start a project")
    assert page.locator("input[placeholder*='claims-repo']").count() == 0
    page.fill("input[placeholder='e.g. payments-masking']", "Payments Masking")
    page.fill("input[placeholder^='C:'][placeholder$='payments-masking']", str(tmp_path / "pm"))
    page.click("button:has-text('Create and open')")
    page.wait_for_selector("textarea[aria-label=Message]")
    assert "Payments Masking" in page.inner_text("nav[aria-label=Projects]")

    page.click("button:has-text('Home')")
    page.wait_for_selector("text=Start a project")
    page.click("[role=radio]:has-text('From an existing repository')")
    assert page.locator("input[placeholder*='claims-repo']").count() == 1
    assert page.locator("input[placeholder^='Acme']").count() == 0  # sensitive terms: standalone only
    page.fill("input[placeholder='e.g. payments-masking']", "Claims export")
    page.fill("input[placeholder^='C:'][placeholder$='payments-masking']", str(tmp_path / "ce"))
    page.fill("input[placeholder*='claims-repo']", str(original_repo))
    page.click("button:has-text('Create and open')")
    page.wait_for_selector("textarea[aria-label=Message]")
    assert not page.problems, page.problems  # type: ignore[attr-defined]


def test_react_ui_in_edge(server: ServerSecurity, tmp_path: Path) -> None:
    # The React UI (ui-react, built into src/forge/web/react): same CSP and token rules as the classic UI.
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
        page.wait_for_selector("text=Start a project")
        page.wait_for_selector("text=Environment check")
        page.screenshot(path=str(shots / "home-dark.png"))
        page.fill("input[placeholder='e.g. payments-masking']", "Payments Masking")
        page.fill("input[placeholder*='payments-masking'][placeholder^='C:']", str(tmp_path / "pm"))
        page.click("button:has-text('Create and open')")
        page.wait_for_selector("textarea[aria-label=Message]")
        page.fill("textarea[aria-label=Message]", "/help")
        page.keyboard.press("Enter")
        page.wait_for_selector("pre:has-text('/rewind')")
        for tab in ("Files", "Diffs", "Learning", "Usage", "Settings", "Tasks"):
            page.click(f"[role=tab]:has-text('{tab}')")
        page.wait_for_selector("text=Phase")
        page.screenshot(path=str(shots / "chat-dark.png"))
        page.click("button[aria-label='Light theme']")
        page.wait_for_timeout(400)  # let the 150 ms colour transitions finish
        page.screenshot(path=str(shots / "chat-light.png"))
        assert "Payments Masking" in page.inner_text("nav[aria-label=Projects]")
        browser.close()
    assert not problems, problems


PLAN = """# Plan

1. **T1** — `payments/security/masking.py`: `mask_pan(pan, visible=4, mask_char="*")` keeps spaces and dashes.
2. **T2** — tests in `tests/payments/security/test_masking.py` (12-19 digits, separators, errors).

| Task | Files | Tests |
|---|---|---|
| T1 | masking.py | 9 |
| T2 | test_masking.py | 7 |
"""


def test_react_chat_cards_render(server: ServerSecurity, workspace: Workspace) -> None:
    # A replayed conversation: markdown answer, tool cards, a plan approval and a question.
    import asyncio

    from forge.engine.events import EventBus, EventType

    async def script() -> None:
        bus = EventBus(workspace.forge_dir / "transcripts" / "events.jsonl", redactor=Redactor())
        await bus.publish(
            EventType.USER_MESSAGE, {"text": "Write mask_pan(pan, visible=4, mask_char='*') -> str"}
        )
        await bus.publish(
            EventType.TOOL_CALL_STARTED, {"id": "c1", "name": "profile_read", "summary": "read PROFILE"}
        )
        await bus.publish(
            EventType.TOOL_CALL_FINISHED,
            {
                "id": "c1",
                "name": "profile_read",
                "ok": True,
                "summary": "read PROFILE",
                "preview": "## 1. Stack & versions\n(unknown)",
                "duration_s": 0.02,
            },
        )
        await bus.publish(
            EventType.TOOL_CALL_STARTED, {"id": "c2", "name": "run_tests", "summary": "run tests tests/"}
        )
        await bus.publish(
            EventType.TOOL_CALL_FINISHED,
            {
                "id": "c2",
                "name": "run_tests",
                "ok": False,
                "summary": "run tests tests/",
                "preview": "pytest: 1 failed, 8 passed",
                "duration_s": 2.4,
            },
        )
        await bus.publish(
            EventType.MESSAGE_DONE,
            {
                "text": 'I\'ll keep your signature **exactly** as given and stub `log_event` for the tests:\n\n```python\ndef mask_pan(pan: str, visible: int = 4, mask_char: str = "*") -> str:\n    ...\n```'
            },
        )
        await bus.publish(
            EventType.APPROVAL_REQUESTED, {"id": "A1", "kind": "plan", "markdown": PLAN, "summary": "plan"}
        )
        await bus.publish(
            EventType.QUESTION_ASKED,
            {
                "id": "Q1",
                "question": "Should masking keep the first 6 digits (BIN)?",
                "context": "PCI DSS allows showing the first 6 and last 4.",
                "options": [
                    {"label": "Last 4 only", "description": "Safest; matches the signature's default."},
                    {
                        "label": "First 6 + last 4",
                        "description": "Useful for routing analytics.",
                        "risks": "Needs a PCI review.",
                    },
                ],
                "recommended": "Last 4 only",
            },
        )

    asyncio.run(script())
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        problems: list[str] = []
        page.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Start a project")
        page.evaluate(
            "p => fetch('/api/open', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({workspace: p})})",
            str(workspace.root),
        )
        page.reload()
        page.wait_for_selector("text=Approve the plan?")
        page.wait_for_selector("text=Should masking keep the first 6 digits (BIN)?")
        page.wait_for_selector("td:has-text('masking.py')")  # markdown table rendered (sanitised)
        page.click("button:has-text('run_tests')")
        page.wait_for_selector("pre:has-text('1 failed')")
        page.screenshot(path=str(shots / "cards-dark.png"), full_page=True)
        browser.close()
    assert not problems, problems


def test_react_composer_features(server: ServerSecurity, workspace: Workspace, tmp_path: Path) -> None:
    # Attach (file picker), @-file suggestions, Shift+Tab mode cycling, history, and the attachment reaching Forge.
    signature = tmp_path / "signature.py"
    signature.write_text("def mask_pan(pan: str, visible: int = 4) -> str: ...\n", encoding="utf-8")
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        problems: list[str] = []
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Start a project")
        page.evaluate(
            "p => fetch('/api/open', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({workspace: p})})",
            str(workspace.root),
        )
        page.reload()
        box = page.locator("textarea[aria-label=Message]")
        box.wait_for()

        page.set_input_files("input[type=file]", str(signature))
        page.wait_for_selector("span[title^='.forge/inputs/']:has-text('signature.py')")

        box.click()
        box.type("Use @claims_se")
        page.wait_for_selector("[role=listbox][aria-label=Files] >> text=claims_service.py")
        page.keyboard.press("Tab")
        assert "@backend/claims_app/services/claims_service.py " in box.input_value()

        page.wait_for_selector("text=default mode")
        page.keyboard.press("Shift+Tab")
        page.wait_for_selector("text=auto mode", timeout=5000)

        page.keyboard.press("Enter")
        page.wait_for_selector("text=Attached:")  # Forge resolved both mentions before calling the model
        notice = page.inner_text("text=Attached:")
        assert "claims_service.py" in notice and ".forge/inputs/" in notice
        assert page.locator("span[title^='.forge/inputs/']").count() == 0  # chips cleared after sending

        box.click()
        page.keyboard.press("ArrowUp")
        assert box.input_value().startswith("Use @backend/claims_app/services/claims_service.py")
        browser.close()
    assert not problems, problems
    stored = list((workspace.forge_dir / "inputs").glob("*-signature.py"))
    assert stored and "mask_pan" in stored[0].read_text(encoding="utf-8")


def test_react_live_progress_and_activity(isolated_forge_home: Path, workspace: Workspace) -> None:
    # Live events (not a replay) drive the progress header and the activity line.
    import asyncio

    from forge.engine.events import EventType

    loops: list[asyncio.AbstractEventLoop] = []
    port = free_port(8798)
    security = ServerSecurity(port=port)
    manager = WebSessionManager(
        isolated_forge_home,
        lambda ws: SessionHost(
            mocked_router(unreachable),
            EventBus(ws.forge_dir / "transcripts" / "events.jsonl", redactor=Redactor()),
            workspace=ws,
            orchestrated=True,
        ),
    )
    app = create_app(manager, security)

    @app.on_event("startup")
    async def remember_loop() -> None:
        loops.append(asyncio.get_running_loop())

    uv = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", ws="websockets-sansio")
    )
    thread = threading.Thread(target=uv.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not uv.started and time.monotonic() < deadline:
        time.sleep(0.05)

    def publish(kind: EventType, payload: dict[str, object]) -> None:
        assert manager.host is not None
        asyncio.run_coroutine_threadsafe(manager.host.bus.publish(kind, payload), loops[0]).result(timeout=5)

    tasks = [
        {"id": "T1", "title": "Masking function", "status": "done"},
        {"id": "T2", "title": "Separators kept", "status": "done"},
        {"id": "T3", "title": "Audit call without the PAN", "status": "in_progress"},
        {"id": "T4", "title": "Validation errors", "status": "pending"},
    ]
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    try:
        with playwright_api.sync_playwright() as p:
            try:
                browser = p.chromium.launch(channel="msedge", headless=True)
            except Exception as error:
                pytest.skip(f"headless Edge not available: {error}")
            page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
            page.goto(security.url())
            page.wait_for_selector("text=Start a project")
            page.evaluate(
                "p => fetch('/api/open', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({workspace: p})})",
                str(workspace.root),
            )
            page.reload()
            page.wait_for_selector("textarea[aria-label=Message]")
            page.wait_for_timeout(500)
            from forge.agent.state import Phase, Task

            assert manager.host is not None and manager.host.orchestrator is not None
            state = manager.host.orchestrator.state  # what /api/state reports, as in a real run
            state.phase, state.current_task = Phase.EXECUTE, "T3"
            state.tasks = [Task(id=t["id"], title=t["title"], status=t["status"]) for t in tasks]
            publish(EventType.STATUS_CHANGED, {"state": "working"})
            publish(EventType.TASK_LIST_UPDATED, {"phase": "execute", "current_task": "T3", "tasks": tasks})
            page.wait_for_selector("[aria-current=step]:has-text('Build')")
            page.wait_for_selector("text=Task 3 of 4")
            page.wait_for_selector("text=2/4 done")
            page.wait_for_selector("[role=status]:has-text('Working on: Audit call without the PAN')")
            publish(
                EventType.TOOL_CALL_STARTED,
                {"id": "t1", "name": "run_tests", "summary": "run tests tests/test_masking.py"},
            )
            page.wait_for_selector("[role=status]:has-text('Running tests')")
            assert "tests/test_masking.py" in page.inner_text("[role=status]")
            page.wait_for_timeout(1200)
            page.screenshot(path=str(shots / "activity-dark.png"))
            publish(
                EventType.TOOL_CALL_FINISHED,
                {"id": "t1", "name": "run_tests", "ok": True, "summary": "run tests", "duration_s": 3.1},
            )
            publish(
                EventType.QUESTION_ASKED,
                {"id": "Q9", "question": "Keep the BIN?", "options": [{"label": "No"}], "recommended": "No"},
            )
            page.wait_for_selector("[role=status]:has-text('Waiting for your answer')")
            # The cost counts up to each new total (animated), then settles on the exact value.
            publish(EventType.COST_UPDATED, {"total_usd": 0.0125, "budget_usd": 5.0, "calls": 3})
            page.wait_for_selector("span[title^='Estimated cost'] >> text=$0.0125")
            publish(EventType.COST_UPDATED, {"total_usd": 0.5578, "budget_usd": 5.0, "calls": 52})
            page.wait_for_selector("span[title^='Estimated cost'] >> text=$0.5578", timeout=5000)
            # Tokens and cost per reply, task and phase, colour-coded by the config limits (D-118).
            bucket = lambda i, o, c, n: {"input_tokens": i, "output_tokens": o, "cost_usd": c, "calls": n}  # noqa: E731
            summary = {
                "total_usd": 0.5578,
                "budget_usd": 5.0,
                "calls": 52,
                "project": {
                    "total": bucket(402_000, 55_000, 0.5578, 52),
                    "by_phase": {
                        "clarify": bucket(18_000, 2_000, 0.02, 3),
                        "execute": bucket(310_000, 41_000, 0.34, 30),
                    },
                    "by_task": {
                        "T1": bucket(40_000, 5_000, 0.04, 6),
                        "T3": bucket(700_000, 60_000, 0.61, 12),
                    },
                },
            }
            publish(EventType.NOTICE, {"kind": "usage", "summary": summary, "cost_usd": 0.01})
            publish(
                EventType.MESSAGE_DONE,
                {
                    "text": "T3 is done.",
                    "usage": {"input_tokens": 12_400, "output_tokens": 1_100},
                    "cost_usd": 0.0138,
                },
            )
            page.wait_for_selector("text=13.5k tok · $0.0138")  # the reply's own usage
            page.wait_for_selector("[aria-current=step] >> xpath=.. >> text=$0.34")
            page.click("[role=tab]:has-text('Tasks')")
            t3 = page.locator("[role=tabpanel] li:has-text('Audit call without the PAN')")
            assert "760k tok" in t3.inner_text()
            assert (
                t3.locator("[aria-label='red usage']").count() == 1
            )  # 0.61 USD / 760k tokens: over the task limits
            assert (
                page.locator(
                    "[role=tabpanel] li:has-text('Masking function') [aria-label='green usage']"
                ).count()
                == 1
            )
            page.click("[role=tab]:has-text('Usage')")
            page.wait_for_selector("[role=tabpanel] td:has-text('Build')")
            page.wait_for_selector("[role=tabpanel] td:has-text('T3 Audit call without the PAN')")
            page.screenshot(path=str(shots / "usage-dark.png"))
            publish(EventType.STATUS_CHANGED, {"state": "idle"})
            page.wait_for_selector("[role=status]", state="detached")
            browser.close()
    finally:
        uv.should_exit = True
        thread.join(timeout=10)
