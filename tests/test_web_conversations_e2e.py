"""D-582 in headless Edge: the conversation dropdown in the top bar (list, new, switch back, rename, and the
card that asks before a running conversation is stopped). Screenshots go to test-artifacts/react-ui/."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

from forge.engine.session_host import SessionHost
from forge.protocol.events import EventBus
from forge.safety.redact import Redactor
from forge.safety.server_security import ServerSecurity
from forge.web.manager import WebSessionManager
from forge.web.server import create_app
from forge.workspace.conversations import ConversationStore
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace
from tests.conftest import REPO_ROOT
from tests.helpers import mocked_router
from tests.test_web import unreachable
from tests.test_web_e2e import configured_secrets, free_port, playwright_api  # noqa: F401

pytestmark = pytest.mark.e2e


@pytest.fixture
def workspace(original_repo: Path, tmp_path: Path) -> Workspace:
    ws = create_workspace(original_repo, tmp_path / "ws", "backend")
    log = ws.forge_dir / "transcripts" / "events.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "seq": 1,
        "type": "user_message",
        "ts": "2026-01-01T00:00:00.000+00:00",
        "payload": {"text": "fix the token limit"},
    }
    log.write_text(json.dumps(event) + "\n", encoding="utf-8")
    return ws


@pytest.fixture
def server(isolated_forge_home: Path) -> Iterator[ServerSecurity]:
    def session(ws: Workspace) -> SessionHost:
        store = ConversationStore(ws)
        bus = EventBus(store.events_path(store.active().id), redactor=Redactor())
        return SessionHost(mocked_router(unreachable), bus, workspace=ws)

    port = free_port(0)
    security = ServerSecurity(port=port)
    manager = WebSessionManager(isolated_forge_home, session)
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
    thread.join(timeout=5)


def test_the_conversation_dropdown(
    server: ServerSecurity, workspace: Workspace, monkeypatch: pytest.MonkeyPatch
) -> None:
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    post = (
        "async ([path, body]) => (await fetch(path, {method: 'POST',"
        " headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})).status"
    )
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        problems: list[str] = []
        # the busy answer is a 409 on purpose; the browser logs it
        page.on(
            "console",
            lambda m: problems.append(m.text) if m.type == "error" and "409" not in m.text else None,
        )
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Start something new.")
        assert page.evaluate(post, ["/api/open", {"workspace": str(workspace.root)}]) == 200
        page.reload()
        switcher = page.get_by_role("button", name="Conversations")
        switcher.wait_for()
        page.wait_for_selector("text=fix the token limit")
        assert "fix the token limit" in switcher.inner_text()

        # The list: new on top, the open conversation marked.
        switcher.click()
        menu = page.get_by_role("menu", name="Conversations")
        menu.wait_for()
        assert menu.get_by_role("menuitem").first.inner_text().strip() == "New conversation"
        assert "open" in menu.inner_text() and "fix the token limit" in menu.inner_text()
        page.screenshot(path=str(shots / "conversations-list.png"))

        # A new conversation has an empty chat.
        menu.get_by_role("menuitem", name="New conversation", exact=True).click()
        page.wait_for_function(
            "() => !document.body.innerText.includes('fix the token limit')", timeout=15000
        )
        assert "New conversation" in switcher.inner_text()
        page.screenshot(path=str(shots / "conversations-new.png"))

        # The first one comes back with its chat.
        switcher.click()
        page.get_by_role("menu", name="Conversations").get_by_role(
            "menuitem", name="fix the token limit"
        ).click()
        page.wait_for_function(
            "() => document.querySelectorAll('[aria-label=Conversations]')[0].innerText.includes('fix the token limit')",
            timeout=15000,
        )
        page.wait_for_selector("text=fix the token limit >> nth=1")  # the title and the message in the chat

        # Rename.
        switcher.click()
        page.get_by_role("button", name="Rename fix the token limit").click(force=True)
        page.get_by_label("Conversation name").fill("Token limit work")
        page.get_by_label("Conversation name").press("Enter")
        page.wait_for_function(
            "() => document.querySelector('[aria-label=Conversations]').innerText.includes('Token limit work')",
            timeout=15000,
        )
        page.keyboard.press("Escape")

        # A switch while DebCraft works asks first.
        monkeypatch.setattr(SessionHost, "busy", property(lambda self: getattr(self, "_pretend", True)))

        async def stop(self: SessionHost) -> None:
            self._pretend = False  # type: ignore[attr-defined]

        monkeypatch.setattr(SessionHost, "interrupt", stop)
        switcher.click()
        page.get_by_role("menuitem", name="New conversation", exact=True).click()
        page.get_by_role("alertdialog", name="Stop and switch").wait_for()
        page.screenshot(path=str(shots / "conversations-busy.png"))
        page.get_by_role("button", name="Keep working").click()
        assert page.get_by_role("alertdialog", name="Stop and switch").count() == 0
        page.get_by_role("menuitem", name="New conversation", exact=True).click()
        page.get_by_role("button", name="Stop and switch").click()
        page.wait_for_function(
            "() => document.querySelector('[aria-label=Conversations]').innerText.includes('New conversation')",
            timeout=15000,
        )
        browser.close()
    assert not problems, problems
