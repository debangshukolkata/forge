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

from forge.config import load_config
from forge.doctor import required_secret_names
from forge.engine.session_host import SessionHost
from forge.protocol.events import EventBus
from forge.safety.redact import Redactor
from forge.safety.server_security import ServerSecurity
from forge.web.manager import WebSessionManager
from forge.web.run import free_port
from forge.web.server import create_app
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace
from tests.conftest import REPO_ROOT
from tests.helpers import mocked_router

pytestmark = pytest.mark.e2e
playwright_api = pytest.importorskip("playwright.sync_api")


def unreachable(request: object) -> object:
    raise AssertionError("no LLM call expected")


@pytest.fixture(autouse=True)
def configured_secrets(isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake values for every required key, so the UI shows its normal pages and not the first-run setup
    screen (D-146), which an empty Forge home would otherwise trigger."""
    for name in required_secret_names(load_config(isolated_forge_home)):
        monkeypatch.setenv(name, "https://fake.invalid")  # check_secrets: fake


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
    page.wait_for_selector("text=Start something new.")

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
    page.click("button:has-text('New project')")
    page.wait_for_selector("text=Create and open")
    assert page.locator("input[placeholder*='claims-repo']").count() == 0
    page.fill("input[placeholder='e.g. payments-masking']", "Payments Masking")
    page.fill("input[placeholder^='C:'][placeholder$='payments-masking']", str(tmp_path / "pm"))
    page.click("button:has-text('Create and open')")
    page.wait_for_selector(
        "textarea[aria-label=Message]", timeout=120_000
    )  # the repo copy is slow under parallel load
    assert "Payments Masking" in page.inner_text("nav[aria-label=Projects]")

    page.click("button:has-text('Home')")
    page.click("button:has-text('New project')")
    page.wait_for_selector("text=Create and open")
    page.click("[role=radio]:has-text('From an existing repository')")
    assert page.locator("input[placeholder*='claims-repo']").count() == 1
    assert page.locator("input[placeholder^='Acme']").count() == 0  # sensitive terms: standalone only
    page.fill("input[placeholder='e.g. payments-masking']", "Claims export")
    page.fill("input[placeholder^='C:'][placeholder$='payments-masking']", str(tmp_path / "ce"))
    page.fill("input[placeholder*='claims-repo']", str(original_repo))
    page.click("button:has-text('Create and open')")
    page.wait_for_selector(
        "textarea[aria-label=Message]", timeout=120_000
    )  # the repo copy is slow under parallel load
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
        page.click("button:has-text('New project')")
        page.wait_for_selector("text=Create and open")
        page.wait_for_selector(
            "[role=dialog][aria-label=Environment]"
        )  # the drawer opens beside the form (D-186)
        # Light is the default theme (D-125).
        assert page.evaluate("document.documentElement.classList.contains('dark')") is False
        page.screenshot(path=str(shots / "home-light.png"))
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
        page.screenshot(path=str(shots / "chat-light.png"))
        page.click("button[aria-label='Dark theme']")
        page.wait_for_timeout(400)  # let the 150 ms colour transitions finish
        page.screenshot(path=str(shots / "chat-dark.png"))
        # the choice of dark is remembered across reloads
        page.reload()
        page.wait_for_selector("button[aria-label='Light theme']")
        assert page.evaluate("document.documentElement.classList.contains('dark')") is True
        # The recent list loads after the reload, so wait for it rather than read it at once.
        page.wait_for_selector("nav[aria-label=Projects] >> text=Payments Masking", timeout=5000)
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

    from forge.protocol.events import EventBus, EventType

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
            EventType.APPROVAL_REQUESTED,
            {
                "id": "A1",
                "kind": "plan",
                # A long unbroken code line must scroll inside its block, not widen the chat.
                "markdown": PLAN + "\n\n```\n" + "assert_masked_" * 40 + "\n```",
                "summary": "plan",
            },
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
        page.wait_for_selector("text=Start something new.")
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
        overflow = page.evaluate(
            "() => { const box = document.querySelector('[aria-live=polite]');"
            " return box.scrollWidth - box.clientWidth; }"
        )
        assert overflow <= 0, f"chat scrolls sideways by {overflow}px"
        page.screenshot(path=str(shots / "cards-light.png"), full_page=True)
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
        page.wait_for_selector("text=Start something new.")
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


class LiveServer:
    """A real server over an orchestrated host, with a way to publish events on its loop (as the engine would)."""

    def __init__(self, security: ServerSecurity, manager: WebSessionManager, loop: object) -> None:
        self.security = security
        self.manager = manager
        self.loop = loop

    def publish(self, kind: object, payload: dict[str, object]) -> None:
        import asyncio

        assert self.manager.host is not None
        future = asyncio.run_coroutine_threadsafe(self.manager.host.bus.publish(kind, payload), self.loop)  # type: ignore[arg-type]
        future.result(timeout=5)


@pytest.fixture
def live_server(isolated_forge_home: Path) -> Iterator[LiveServer]:
    import asyncio

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
    try:
        yield LiveServer(security, manager, loops[0])
    finally:
        uv.should_exit = True
        thread.join(timeout=10)


def open_in_edge(p: object, live: LiveServer, workspace: Workspace) -> tuple[object, object]:
    """Headless Edge on the project's chat (skips when Edge isn't installed)."""
    try:
        browser = p.chromium.launch(channel="msedge", headless=True)  # type: ignore[attr-defined]
    except Exception as error:
        pytest.skip(f"headless Edge not available: {error}")
    page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
    problems: list[str] = []
    page.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: problems.append(str(e)))
    page.problems = problems
    page.goto(live.security.url())
    page.wait_for_selector("text=Start something new.")
    page.evaluate(
        "p => fetch('/api/open', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({workspace: p})})",
        str(workspace.root),
    )
    page.reload()
    page.wait_for_selector("textarea[aria-label=Message]")
    page.wait_for_timeout(500)
    return browser, page


@pytest.mark.skip(
    reason="Run map/stepper UI reads the old phase field; redesign deferred (D-131) after the "
    "orchestrator's flat-loop rewrite (D-128). Re-enable once the UI is rebuilt against the new "
    "activity/cadence fields."
)
def test_react_live_progress_and_activity(live_server: LiveServer, workspace: Workspace) -> None:
    # Live events (not a replay) drive the progress header and the activity line.
    from forge.protocol.events import EventType

    manager, publish = live_server.manager, live_server.publish

    tasks = [
        {"id": "T1", "title": "Masking function", "status": "done"},
        {"id": "T2", "title": "Separators kept", "status": "done"},
        {"id": "T3", "title": "Audit call without the PAN", "status": "in_progress"},
        {"id": "T4", "title": "Validation errors", "status": "pending"},
    ]
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    with playwright_api.sync_playwright() as p:
        browser, page = open_in_edge(p, live_server, workspace)
        from forge.workflow.state import Task

        assert manager.host is not None and manager.host.orchestrator is not None
        state = manager.host.orchestrator.state  # what /api/state reports, as in a real run
        state.current_task = "T3"
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
        # The current step animates while Forge works on it (D-121).
        page.wait_for_selector("[aria-current=step] [data-motion=step-working]")
        assert "tests/test_masking.py" in page.inner_text("[role=status]")
        page.wait_for_timeout(1200)
        page.screenshot(path=str(shots / "activity-light.png"))
        publish(
            EventType.TOOL_CALL_FINISHED,
            {"id": "t1", "name": "run_tests", "ok": True, "summary": "run tests", "duration_s": 3.1},
        )
        publish(
            EventType.QUESTION_ASKED,
            {"id": "Q9", "question": "Keep the BIN?", "options": [{"label": "No"}], "recommended": "No"},
        )
        page.wait_for_selector("[role=status]:has-text('Waiting for your answer')")
        page.wait_for_selector("[aria-current=step] [data-motion=step-waiting]")
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
            page.locator("[role=tabpanel] li:has-text('Masking function') [aria-label='green usage']").count()
            == 1
        )
        page.click("[role=tab]:has-text('Usage')")
        page.wait_for_selector("[role=tabpanel] td:has-text('Build')")
        page.wait_for_selector("[role=tabpanel] td:has-text('T3 Audit call without the PAN')")
        page.screenshot(path=str(shots / "usage-light.png"))
        publish(EventType.STATUS_CHANGED, {"state": "idle"})
        page.wait_for_selector("[role=status]", state="detached")
        browser.close()


@pytest.mark.skip(
    reason="Run map reads the old phase field; redesign deferred (D-131) after the orchestrator's "
    "flat-loop rewrite (D-128). Re-enable once the UI is rebuilt against the new activity/cadence fields."
)
def test_react_run_map(live_server: LiveServer, workspace: Workspace) -> None:
    # The Run map (D-119) draws the plan, helper agents, failures, stuck warnings and waits from the events.
    from forge.protocol.events import EventType
    from forge.workflow.state import Task

    publish = live_server.publish
    tasks = [
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
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    with playwright_api.sync_playwright() as p:
        browser, page = open_in_edge(p, live_server, workspace)
        # The side panel collapses to a rail of tab icons; an icon reopens it on that tab; the choice survives a reload.
        page.click("[aria-label='Hide the side panel']")
        page.wait_for_selector("aside[aria-label='Details (collapsed)']")
        page.reload()
        page.wait_for_selector("aside[aria-label='Details (collapsed)']")
        page.click("[aria-label='Open Usage']")
        page.wait_for_selector("aside[aria-label=Details] [role=tab][aria-selected=true]:has-text('Usage')")
        assert live_server.manager.host is not None and live_server.manager.host.orchestrator is not None
        state = live_server.manager.host.orchestrator.state

        def at(activity: str, task: str | None = None) -> None:  # events are stamped with the current task
            state.current_task = task

        at("clarify")
        publish(EventType.USER_MESSAGE, {"text": "Mask card numbers in the audit log"})
        publish(
            EventType.QUESTION_ASKED,
            {"id": "Q1", "question": "Keep the last four digits?", "options": [{"label": "Yes"}]},
        )
        at("plan")
        state.tasks = [Task.model_validate(t) for t in tasks]
        publish(EventType.TASK_LIST_UPDATED, {"phase": "plan", "current_task": None, "tasks": tasks})
        at("execute", "T1")
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
        # the same tool succeeds later in T1: that failure was fixed
        publish(EventType.TOOL_CALL_STARTED, {"id": "c2", "name": "run_tests", "summary": "run tests"})
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
            },
        )
        at("execute", "T2")
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
        at("execute", "T3")
        publish(EventType.STATUS_CHANGED, {"state": "working"})
        publish(
            EventType.AGENT_STARTED,
            {"id": "agent-2", "role": "helper", "purpose": "Helper task: find the audit call"},
        )
        publish(EventType.TASK_LIST_UPDATED, {"phase": "execute", "current_task": "T3", "tasks": tasks})
        publish(
            EventType.APPROVAL_REQUESTED,
            {"id": "A7", "title": "Approve the audit change", "body": "…", "options": ["approve", "reject"]},
        )

        page.click("[role=tab]:has-text('Run map')")
        page.wait_for_selector("[data-testid=run-map]")
        page.wait_for_selector("[data-task=T1][data-status=done]")
        assert page.locator("[data-task]").count() == 5
        page.wait_for_selector("[data-task=T2] >> text=Blocked: needs the card format from you")
        assert (
            page.locator("[data-step=review]").count() == 1
            and page.locator("[data-step=deliver]").count() == 1
        )
        # T1 → T2, T1 → T3, T2/T3 → T4, Plan → T1, T4 → Review, Review → FIX1, FIX1 → Deliver
        assert page.locator(".react-flow__edge").count() == 8
        assert page.locator(".run-edge-fix").count() == 1
        assert page.locator("[data-task=T1] [title='Failed tool calls']").inner_text().strip() == "1"
        assert page.locator("[data-task=T1] [title='Helper agents']").inner_text().strip() == "1"
        assert page.locator("[data-marker=failure]").count() == 2
        assert page.locator("[data-marker=stuck]").count() == 1
        # Waiting for you: a bar from each request to your answer; the open one grows until you answer (D-123)
        assert page.locator("[data-marker=waiting]").count() == 2
        assert page.locator("[data-span=waiting]").count() == 2
        timeline = page.inner_text("[data-testid=run-timeline]")
        assert "Debugger" in timeline and "Helper" in timeline and "T3" in timeline
        assert "Waiting for you" in timeline
        page.wait_for_selector("[data-testid=run-map-waiting]:has-text('Approval needed')")
        page.wait_for_selector("text=2 failed calls")
        page.wait_for_selector("text=2 agents · 1 running")
        page.wait_for_timeout(600)
        page.screenshot(path=str(shots / "run-map-light.png"))
        page.click("[aria-label='Dark theme']")
        page.wait_for_timeout(300)
        page.screenshot(path=str(shots / "run-map-dark.png"))

        # What failed (D-122): the chip opens a drawer with every failure, grouped by task.
        page.click("button[title='See what failed']")
        drawer = page.locator("[data-testid=failure-drawer]")
        drawer.wait_for()
        assert drawer.locator("[data-failure]").count() == 2
        fixed = drawer.locator("[data-outcome=fixed]")
        assert "Tests failed" in fixed.inner_text() and "Fixed later" in fixed.inner_text()
        # the error is at the end of the output: the preview shows the last lines, Show more the rest
        assert "AssertionError" in fixed.inner_text() and "collected 9 items" not in fixed.inner_text()
        fixed.locator("text=Show more").click()
        assert "collected 9 items" in fixed.inner_text()
        blocked = drawer.locator("[data-outcome=open]")
        assert "Blocked or declined" in blocked.inner_text() and "Not fixed yet" in blocked.inner_text()
        page.wait_for_timeout(400)
        page.screenshot(path=str(shots / "failures-drawer-dark.png"))
        page.keyboard.press("Escape")
        drawer.wait_for(state="detached")
        # A task's failure count opens the drawer for that task only.
        page.click("[aria-label='See the 1 failed call of T2']")
        drawer.wait_for()
        assert drawer.locator("[data-failure]").count() == 1
        assert "edit src/mask.py" in drawer.inner_text()
        page.keyboard.press("Escape")
        # Clicking a task card jumps to its first event in the chat.
        page.click("[data-task=T1]")
        page.wait_for_selector(".jump-flash")
        page.click("[role=tab]:has-text('Run map')")
        page.wait_for_selector("[data-testid=run-map]")
        # A failure marker opens the drawer on that failure; "Show in chat" jumps to its row.
        page.locator("[data-marker=failure]").first.click()
        drawer.wait_for()
        drawer.locator("li.ring-2 >> text=Show in chat").click()
        page.wait_for_selector("textarea[aria-label=Message]")
        page.wait_for_selector(".jump-flash")
        assert "run tests" in page.inner_text(".jump-flash").lower()
        assert not page.problems, page.problems  # type: ignore[attr-defined]
        browser.close()
