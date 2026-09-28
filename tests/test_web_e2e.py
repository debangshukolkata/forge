"""M9W end-to-end in headless Edge (spec §15A.6) against a real uvicorn server — the UI mechanics that don't
need the model: token login, opening a workspace, slash commands, panels, diff view, reload replay, output.zip
download, Stop, and no JavaScript/CSP errors. The model-driven run through the web UI is in
test_live_web_e2e.py."""

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
    page.wait_for_selector("#home:not([hidden])")
    page.wait_for_selector("#doctor li")

    # Open the workspace through the API the home screen uses, then load it like a user would.
    page.evaluate("p => window.forgeApp.open(p)", str(workspace.root))
    page.wait_for_selector("#chat-view:not([hidden])")
    page.fill("#input", "/help")
    page.keyboard.press("Enter")
    page.wait_for_selector("#chat .notice pre:has-text('/rewind')")

    page.click("#tabs button[data-tab=files]")
    page.wait_for_selector(".tree span:has-text('backend')")
    page.click("#tabs button[data-tab=diffs]")
    page.wait_for_selector(".d2h-wrapper")
    assert "edited for the e2e test" in page.inner_text("#tab-body")
    page.click("#tabs button[data-tab=learning]")
    page.wait_for_selector("#tab-body h4:has-text('Lessons')")
    page.click("#tabs button[data-tab=settings]")
    page.wait_for_selector("#tab-body select")

    page.reload()  # state is replayed from the event log
    page.wait_for_selector("#chat .notice pre:has-text('/rewind')")

    with page.expect_download() as download:
        page.click("#tabs button[data-tab=files]")
        page.click("text=Download output.zip")
    assert download.value.suggested_filename.endswith("-output.zip")

    page.click("#btn-stop")  # nothing running: the engine takes it without error
    time.sleep(0.5)
    assert page.problems == [], page.problems  # type: ignore[attr-defined]


def test_new_project_form_in_edge(page, server: ServerSecurity, tmp_path: Path, original_repo: Path) -> None:  # type: ignore[no-untyped-def]
    # The start form: project name + folder (both modes); the repository field appears only in Mode A.
    page.goto(server.url())
    page.wait_for_selector("#home:not([hidden])")
    assert page.is_hidden("#new-project input[name=repo]")
    page.fill("#new-project input[name=project]", "Payments Masking")
    page.fill("#new-project input[name=folder]", str(tmp_path / "pm"))
    page.click("#new-project button[type=submit]")
    page.wait_for_selector("#chat-view:not([hidden])")
    assert "Payments Masking" in page.inner_text("#recent")

    page.click("#btn-home")
    page.wait_for_selector("#home:not([hidden])")
    page.check("#new-project input[name=mode][value=A]")
    assert page.is_visible("#new-project input[name=repo]")
    assert page.is_hidden("#new-project input[name=sensitive_terms]")
    page.fill("#new-project input[name=project]", "Claims export")
    page.fill("#new-project input[name=folder]", str(tmp_path / "ce"))
    page.fill("#new-project input[name=repo]", str(original_repo))
    page.click("#new-project button[type=submit]")
    page.wait_for_selector("#chat-view:not([hidden])")
    assert not page.problems, page.problems  # type: ignore[attr-defined]


@pytest.fixture
def react_server(isolated_forge_home: Path) -> Iterator[ServerSecurity]:
    port = free_port(8796)
    security = ServerSecurity(port=port)
    manager = WebSessionManager(
        isolated_forge_home,
        lambda ws: SessionHost(
            mocked_router(unreachable),
            EventBus(ws.forge_dir / "transcripts" / "events.jsonl", redactor=Redactor()),
            workspace=ws,
        ),
    )
    app = create_app(manager, security, ui="react")
    uv = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", ws="websockets-sansio")
    )
    thread = threading.Thread(target=uv.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not uv.started and time.monotonic() < deadline:
        time.sleep(0.05)
    yield security
    uv.should_exit = True
    thread.join(timeout=10)


def test_react_ui_in_edge(react_server: ServerSecurity, tmp_path: Path) -> None:
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
        page.goto(react_server.url())
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
        for tab in ("Files", "Diffs", "Learning", "Context", "Settings", "Tasks"):
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


def test_react_chat_cards_render(react_server: ServerSecurity, workspace: Workspace) -> None:
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
        page.goto(react_server.url())
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
