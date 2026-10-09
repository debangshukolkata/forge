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
    port = free_port(0)
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
    assert (
        page.locator("[role=tab]:has-text('Learning')").count() == 0
    )  # retired with the learning module (D-198)
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
    # D-234: no permanent project list in a project; the name in the top bar opens the switcher.
    assert page.locator("nav[aria-label=Projects]").count() == 0
    page.click("header button[aria-haspopup=menu]")
    menu = page.locator("[role=menu][aria-label=Projects]")
    assert "Payments Masking" in menu.inner_text() and "New project" in menu.inner_text()
    page.keyboard.press("Escape")
    menu.wait_for(state="detached")

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
        for tab in ("Files", "Diffs", "Usage", "Settings", "Tasks"):
            page.click(f"[role=tab]:has-text('{tab}')")
        page.wait_for_selector("text=No tasks yet")
        page.screenshot(path=str(shots / "chat-light.png"))
        page.click("button[aria-label='Dark theme']")
        page.wait_for_timeout(400)  # let the 150 ms colour transitions finish
        page.screenshot(path=str(shots / "chat-dark.png"))
        # the choice of dark is remembered across reloads
        page.reload()
        page.wait_for_selector("button[aria-label='Light theme']")
        assert page.evaluate("document.documentElement.classList.contains('dark')") is True
        # The recent list loads after the reload, so wait for it rather than read it at once.
        page.wait_for_selector("header button[aria-haspopup=menu] >> text=Payments Masking", timeout=5000)
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
            EventType.TOOL_CALL_STARTED,
            {
                "id": "c2",
                "name": "run_tests",
                "summary": "run tests tests/",
                "arguments": {"command": "python -m pytest tests/ -q"},
            },
        )
        await bus.publish(
            EventType.TOOL_CALL_FINISHED,
            {
                "id": "c2",
                "name": "run_tests",
                "ok": False,
                "summary": "run tests tests/",
                "preview": "\n".join(f"tests/test_masking.py::test_case_{n} PASSED" for n in range(1, 29))
                + "\npytest: 1 failed, 8 passed",
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
        # A failed call opens by itself: no click needed to see what went wrong.
        page.wait_for_selector("text=python -m pytest tests/ -q")  # the IN block
        assert not page.locator("pre:has-text('1 failed')").count()  # long output is folded
        page.click("button:has-text('more lines')")
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
    port = free_port(0)
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


def test_react_subagent_steps_are_nested(server: ServerSecurity, workspace: Workspace) -> None:
    """D-181: a subagent's own tool calls sit inside its row, collapsed until opened; a running one shows its newest step."""
    import asyncio

    from forge.protocol.events import EventBus, EventType

    async def script() -> None:
        bus = EventBus(workspace.forge_dir / "transcripts" / "events.jsonl", redactor=Redactor())
        await bus.publish(EventType.USER_MESSAGE, {"text": "Review my change and map the auth code"})
        for call_id, who in (("s1", "reviewer"), ("s2", "explore")):
            await bus.publish(
                EventType.TOOL_CALL_STARTED,
                {
                    "id": call_id,
                    "name": "spawn_subagent",
                    "summary": f"spawn {who}",
                    "arguments": {"agent": who, "task": f"{who} task text"},
                },
            )
        await bus.publish(
            EventType.AGENT_STARTED,
            {"id": "agent-1", "role": "reviewer", "purpose": "Review the change: masking.py"},
        )
        await bus.publish(
            EventType.AGENT_STARTED,
            {"id": "agent-2", "role": "explore", "purpose": "Helper task: where is auth?"},
        )
        steps = [
            ("agent-1", {"kind": "thinking", "text": "Checking the signature first"}),
            ("agent-1", {"kind": "tool_started", "name": "run_command", "summary": "python -m pytest -q"}),
            (
                "agent-1",
                {
                    "kind": "tool_finished",
                    "name": "run_command",
                    "ok": False,
                    "summary": "python -m pytest -q",
                    "duration_s": 3.2,
                },
            ),
            ("agent-1", {"kind": "tool_started", "name": "read_file", "summary": "payments/masking.py"}),
            (
                "agent-1",
                {
                    "kind": "tool_finished",
                    "name": "read_file",
                    "ok": True,
                    "summary": "payments/masking.py",
                    "duration_s": 0.1,
                },
            ),
            ("agent-2", {"kind": "tool_started", "name": "grep", "summary": "def authenticate"}),
        ]
        for agent, fields in steps:
            await bus.publish(EventType.SUBAGENT_STEP, {"agent": agent, "role": "x", **fields})
        await bus.publish(
            EventType.AGENT_FINISHED,
            {
                "id": "agent-1",
                "role": "reviewer",
                "ok": True,
                "tool_calls": 2,
                "failed_calls": 1,
                "duration_s": 4.5,
            },
        )
        await bus.publish(
            EventType.TOOL_CALL_FINISHED,
            {
                "id": "s1",
                "name": "spawn_subagent",
                "ok": True,
                "summary": "spawn reviewer",
                "preview": "VERDICT: PASS (one failing test was unrelated)",
                "duration_s": 4.6,
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
        reviewer = page.locator("button:has-text('Review the change: masking.py')")
        explorer = page.locator("button:has-text('where is auth?')")
        reviewer.wait_for()
        explorer.wait_for()
        # Collapsed: a finished agent shows its counts; a running one shows what it is doing right now.
        assert "2 calls, 1 failed" in reviewer.inner_text()
        assert "grep: def authenticate" in explorer.inner_text()
        assert page.locator("ol[aria-label='Reviewer steps']").count() == 0
        # A helper that is still working shows its steps by itself, without a click (D-214).
        running_steps = page.locator("ol[aria-label='Explorer steps']")
        running_steps.wait_for()
        assert "def authenticate" in running_steps.inner_text()
        # The agent was paired with its own spawn row: no extra row was made for it.
        assert page.locator("button:has-text('spawn_subagent')").count() == 0

        reviewer.click()
        steps = page.locator("ol[aria-label='Reviewer steps']")
        steps.wait_for()
        text = steps.inner_text()
        assert (
            "Checking the signature first" in text and "run_command" in text and "payments/masking.py" in text
        )
        page.wait_for_selector("pre:has-text('VERDICT: PASS')")  # the hand-back is the OUT block
        page.wait_for_selector("text=reviewer task text")  # the task is the IN block
        page.screenshot(path=str(shots / "subagent-nested-light.png"))
        browser.close()
    assert not problems, problems


def test_react_todo_list(server: ServerSecurity, workspace: Workspace) -> None:
    """D-177: the model's todo list shows in the Tasks tab (no strip above the message box) and follows the latest update."""
    import asyncio

    from forge.protocol.events import EventBus, EventType

    async def script() -> None:
        bus = EventBus(workspace.forge_dir / "transcripts" / "events.jsonl", redactor=Redactor())
        await bus.publish(EventType.USER_MESSAGE, {"text": "Add a CSV export"})
        first = [
            {"content": "Read the report builder", "status": "in_progress"},
            {"content": "Add export_csv()", "status": "pending"},
            {"content": "Write tests", "status": "pending"},
        ]
        await bus.publish(EventType.TODO_UPDATED, {"items": first})
        later = [
            {"content": "Read the report builder", "status": "completed"},
            {"content": "Add export_csv()", "status": "in_progress"},
            {"content": "Write tests", "status": "pending"},
        ]
        await bus.publish(EventType.TODO_UPDATED, {"items": later})

    asyncio.run(script())
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
        assert (
            page.locator("button[aria-expanded]:has-text('Todo')").count() == 0
        )  # no strip above the message box (D-221)
        page.click("[role=tab]:has-text('Tasks')")
        page.wait_for_selector("text=Forge's todo list")
        page.wait_for_selector("text=1/3 done")
        browser.close()
    assert not problems, problems


def test_react_timeline_rows(server: ServerSecurity, workspace: Workspace) -> None:
    """D-151/D-189: narration between calls, read/search runs folded into one line, edits as inline diffs, failures open."""
    import asyncio

    from forge.protocol.events import EventBus, EventType

    async def call(
        bus: EventBus, call_id: str, name: str, summary: str, ok: bool = True, preview: str = "done"
    ) -> None:
        await bus.publish(
            EventType.TOOL_CALL_STARTED, {"id": call_id, "name": name, "summary": summary, "arguments": {}}
        )
        await bus.publish(
            EventType.TOOL_CALL_FINISHED,
            {
                "id": call_id,
                "name": name,
                "ok": ok,
                "summary": summary,
                "preview": preview,
                "duration_s": 0.2,
            },
        )

    async def script() -> None:
        bus = EventBus(workspace.forge_dir / "transcripts" / "events.jsonl", redactor=Redactor())
        await bus.publish(EventType.USER_MESSAGE, {"text": "Rename the helper and fix the import"})
        await bus.publish(
            EventType.THINKING_DELTA, {"text": "First I will look at where the helper is used."}
        )
        await call(bus, "r1", "grep", "def helper")
        await call(bus, "r2", "read_file", "utils.py")
        await call(bus, "r3", "grep", "helper(")
        await call(bus, "r4", "read_file", "main.py")
        await call(bus, "r5", "glob", "**/*.py")
        await bus.publish(EventType.THINKING_DELTA, {"text": "Two files use it; I will edit both."})
        await bus.publish(
            EventType.TOOL_CALL_STARTED,
            {"id": "e1", "name": "edit_file", "summary": "edit utils.py", "arguments": {"path": "utils.py"}},
        )
        diff = "--- a/utils.py\n+++ b/utils.py\n@@ -1,3 +1,4 @@\n def keep():\n-    return helper()\n+    return helper_v2()\n+    # renamed\n"
        await bus.publish(EventType.FILE_CHANGED, {"path": "utils.py", "op": "update", "diff": diff})
        await bus.publish(
            EventType.TOOL_CALL_FINISHED,
            {
                "id": "e1",
                "name": "edit_file",
                "ok": True,
                "summary": "edit utils.py",
                "preview": "Updated utils.py.",
                "duration_s": 0.1,
            },
        )
        await call(bus, "t1", "run_command", "python -m pytest -q", ok=False, preview="1 failed: test_keep")

    asyncio.run(script())
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
        page.wait_for_selector("text=First I will look at where the helper is used.")  # narration, in order
        page.wait_for_selector("text=Two files use it; I will edit both.")
        group = page.locator("button:has-text('Read 2 files, Searched 3 times')")
        group.wait_for()
        assert page.locator("button:has-text('def helper')").count() == 0  # folded until opened
        # The edit shows its diff without a click, with the +/- counts on the row.
        diff_box = page.locator("[role=region][aria-label=Changes]")
        diff_box.wait_for()
        assert "return helper_v2()" in diff_box.inner_text() and "# renamed" in diff_box.inner_text()
        assert "return helper()" in diff_box.inner_text()
        assert "+2" in page.locator("button:has-text('edit_file')").inner_text()
        # The failed test run opened itself.
        page.wait_for_selector("pre:has-text('1 failed: test_keep')")
        page.screenshot(path=str(shots / "timeline-rows-light.png"))
        group.click()
        page.wait_for_selector("button:has-text('def helper')")
        browser.close()
    assert not problems, problems


def test_react_full_tool_output(server: ServerSecurity, workspace: Workspace) -> None:
    """D-195: a long result shows a preview, and "Show full output" fetches the whole saved text."""
    import asyncio

    from forge.agent.tool_output import FOLDER
    from forge.protocol.events import EventBus, EventType

    saved_id, missing_id = "a" * 32, "b" * 32
    full = "\n".join(f"test_case_{n} PASSED" for n in range(1, 301)) + "\n300 passed in 4.1s"
    folder = workspace.forge_dir / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{saved_id}.txt").write_text(full, encoding="utf-8")

    async def script() -> None:
        bus = EventBus(workspace.forge_dir / "transcripts" / "events.jsonl", redactor=Redactor())
        await bus.publish(EventType.USER_MESSAGE, {"text": "Run the tests"})
        for call_id, output_id in (("t1", saved_id), ("t2", missing_id)):
            await bus.publish(
                EventType.TOOL_CALL_STARTED,
                {
                    "id": call_id,
                    "name": "run_command",
                    "summary": f"pytest {call_id}",
                    "arguments": {"command": "pytest"},
                },
            )
            await bus.publish(
                EventType.TOOL_CALL_FINISHED,
                {
                    "id": call_id,
                    "name": "run_command",
                    "ok": True,
                    "summary": f"pytest {call_id}",
                    "preview": "test_case_1 PASSED\ntest_case_2 PASSED",
                    "duration_s": 4.1,
                    "output_id": output_id,
                    "output_chars": len(full),
                },
            )

    asyncio.run(script())
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        problems: list[str] = []
        # the second call's output was deleted on purpose: the 404 is expected and the UI says so
        page.on(
            "console",
            lambda m: problems.append(m.text) if m.type == "error" and "404" not in m.text else None,
        )
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Start something new.")
        page.evaluate(
            "p => fetch('/api/open', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({workspace: p})})",
            str(workspace.root),
        )
        page.reload()
        page.click("button:has-text('pytest t1')")
        page.wait_for_selector("pre:has-text('test_case_2 PASSED')")
        assert page.locator("pre:has-text('test_case_300 PASSED')").count() == 0  # only the preview so far
        page.click(f"button:has-text('Show full output ({len(full):,} characters)')")
        page.wait_for_selector("pre:has-text('300 passed in 4.1s')")
        page.wait_for_selector(f"text=Full output, {len(full):,} characters")
        page.click("button:has-text('Show less')")
        assert page.locator("pre:has-text('300 passed in 4.1s')").count() == 0

        page.click("button:has-text('pytest t2')")
        page.locator("button:has-text('Show full output')").last.click()  # the second call's
        page.wait_for_selector("text=The full output is no longer available.")
        browser.close()
    assert not problems, problems


def test_react_project_list_shows_what_forge_remembers(
    server: ServerSecurity, isolated_forge_home: Path, tmp_path: Path
) -> None:
    """D-196: each project in the list says where the work stands, from its handoff, and what Forge holds for it."""
    from forge.memory.store import STATE_MEMORY, MemoryStore
    from forge.modeb.profile import ProfileStore

    handoff = (
        "## Goal\nMask card numbers in the audit log.\n\n## Next\n1. Add the CSV export of masked rows\n"
    )
    profile = ProfileStore(isolated_forge_home).create("web-host")
    store = MemoryStore(isolated_forge_home, "profile:web-host")
    store.save(STATE_MEMORY, "Where the work stands", "project", handoff)
    store.save("prefers-pytest", "Uses pytest", "project", "Run python -m pytest -q.")
    (profile.root / "FORGE.md").write_text("# Host rules\n", encoding="utf-8")
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
        problems: list[str] = []
        page.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Start something new.")
        page.evaluate(
            "p => fetch('/api/standalone', {method: 'POST', headers: {'Content-Type': 'application/json'},"
            " body: JSON.stringify({workspace: p, profile: 'web-host'})})",
            str(tmp_path / "wsb"),
        )
        page.reload()
        page.click("button:has-text('Home')")
        page.click("button:has-text('Open a project')")
        state = page.locator("[data-testid=project-state]")
        state.wait_for()
        assert "Mask card numbers in the audit log." in state.inner_text()
        assert "Add the CSV export of masked rows" in state.inner_text()
        card = page.locator("li:has([data-testid=project-state])")
        assert (
            "1 note" in card.inner_text()
            and "FORGE.md" in card.inner_text()
            and "handoff" in card.inner_text()
        )
        page.fill("input[aria-label='Search projects']", "csv export")  # the search reads the handoff too
        assert page.locator("[data-testid=project-state]").count() == 1
        page.fill("input[aria-label='Search projects']", "nothing like this")
        page.wait_for_selector("text=No match")
        page.fill("input[aria-label='Search projects']", "")
        page.screenshot(path=str(shots / "projects-memory-light.png"))
        # D-226: deleting asks first, then removes the project's folder and its row.
        page.click("button[aria-label^='Delete ']")
        page.wait_for_selector("[role=alertdialog]")
        page.screenshot(path=str(shots / "projects-delete-confirm-light.png"))
        page.click("button:has-text('Cancel')")
        assert (tmp_path / "wsb").exists()
        page.click("button[aria-label^='Delete ']")
        page.click("button:has-text('Delete project')")
        page.wait_for_selector("text=No projects yet")
        assert not (tmp_path / "wsb").exists()
        browser.close()
    assert not problems, problems


def test_react_learnings_pick_and_forget(
    server: ServerSecurity, isolated_forge_home: Path, tmp_path: Path
) -> None:
    """D-227: notes are grouped by project; only the ticked ones are forgotten."""
    from forge.memory.store import MemoryStore
    from forge.modeb.profile import ProfileStore

    ProfileStore(isolated_forge_home).create("learn-host")
    store = MemoryStore(isolated_forge_home, "profile:learn-host")
    store.save("uses-pytest", "Uses pytest", "project", "Run python -m pytest -q.")
    store.save("keep-me", "Keep this one", "project", "Stays.")
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
        problems: list[str] = []
        page.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Start something new.")
        page.evaluate(
            "p => fetch('/api/standalone', {method: 'POST', headers: {'Content-Type': 'application/json'},"
            " body: JSON.stringify({workspace: p, profile: 'learn-host'})})",
            str(tmp_path / "wsl"),
        )
        page.reload()
        page.click("button:has-text('Home')")
        page.click("button:has-text('Open a project')")
        page.click("button:has-text('What Forge learned')")
        page.wait_for_selector("text=uses-pytest")
        page.screenshot(path=str(shots / "learnings-light.png"))
        page.check("input[aria-label='Forget uses-pytest']")
        page.click("button:has-text('Forget selected')")
        page.click("button:has-text('Yes, forget')")
        page.wait_for_selector("text=keep-me")
        page.wait_for_selector("text=uses-pytest", state="detached")
        browser.close()
    assert not problems, problems
    assert [m.name for m in store.all()] == ["keep-me"]


def test_react_project_switcher_deletes_from_the_top_bar(
    server: ServerSecurity, isolated_forge_home: Path, tmp_path: Path
) -> None:
    """D-234: the top-bar menu lists recent projects and deletes one (after asking), also the open one."""
    from forge.modeb.profile import ProfileStore

    ProfileStore(isolated_forge_home).create("switch-host")
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
        problems: list[str] = []
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Start something new.")
        page.evaluate(
            "p => fetch('/api/standalone', {method: 'POST', headers: {'Content-Type': 'application/json'},"
            " body: JSON.stringify({workspace: p, profile: 'switch-host'})})",
            str(tmp_path / "wss"),
        )
        page.reload()
        page.click("header button[aria-haspopup=menu]")
        page.screenshot(path=str(shots / "project-switcher-light.png"))
        page.click("button[aria-label^='Delete ']")
        page.wait_for_selector("[role=alertdialog]")
        page.click("button:has-text('Delete project')")
        page.wait_for_selector("text=Start something new.")  # the open project went, so back to Home
        assert not (tmp_path / "wss").exists()
        browser.close()
    assert not problems, problems
