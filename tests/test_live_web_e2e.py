"""M9W live end-to-end (spec §15A.6): a Mode A requirement on the fixture completed using only the web UI in
headless Edge, driven by the real model — answer design-fork cards, approve the plan, reload mid-run and
see the state replayed, watch tasks complete, view a diff, download output.zip, then press Stop on a
change request. Run with: pytest -m live tests/test_live_web_e2e.py"""

from __future__ import annotations

import io
import threading
import time
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

from forge.safety.server_security import ServerSecurity
from forge.session import build_session
from forge.web.manager import WebSessionManager
from forge.web.run import free_port
from forge.web.server import create_app
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace
from tests.conftest import FIXTURE_BACKEND, FIXTURE_REPO, REPO_ROOT

pytestmark = [pytest.mark.live, pytest.mark.e2e]
playwright_api = pytest.importorskip("playwright.sync_api")
FIXTURE_PYTHON = FIXTURE_BACKEND / "venv" / "Scripts" / "python.exe"
REQUIREMENT = (
    "Add GET /api/policies/{policy_id}/claims/count returning {policy_id, claim_count} for one policy "
    "(404 if the policy doesn't exist). Follow the existing layering (repository with raw SQL, service, "
    "route with marshmallow schemas) and add tests. No authentication changes."
)
RUN_TIMEOUT_S = 1500
USER_REPLY = "Use your recommended option for every open question, note the assumptions, and continue."


@pytest.fixture
def workspace(tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch) -> Workspace:
    if not FIXTURE_PYTHON.exists():
        pytest.skip("run scripts/dev/setup_fixture_venv.ps1 first")
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    return create_workspace(FIXTURE_REPO, tmp_path / "ws_web", "backend")


@pytest.fixture
def server(isolated_forge_home: Path, workspace: Workspace) -> Iterator[ServerSecurity]:
    port = free_port(8791)
    security = ServerSecurity(port=port)
    manager = WebSessionManager(
        isolated_forge_home, lambda ws: build_session(workspace=ws, orchestrated=True)
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
    thread.join(timeout=30)


def answer_waiting_cards(page) -> int:  # type: ignore[no-untyped-def]
    """Clicks through whatever Forge is waiting for, like a user accepting the recommendations."""
    clicked = 0
    for card in page.query_selector_all("[data-card][data-pending]"):
        kind = card.get_attribute("data-card")
        if kind == "question":
            button = card.query_selector("button[data-recommended]") or card.query_selector(
                "button:has(span)"
            )
        elif kind == "approval":
            button = card.query_selector("button:has-text('Approve')") or card.query_selector(
                "button:has-text('Allow once')"
            )
        else:  # user action: this test can't do OS-level steps
            button = card.query_selector('button:has-text("I can\'t")')
        if button is not None and button.is_enabled():
            button.click()
            clicked += 1
    return clicked


def keep_evidence(page, workspace: Workspace) -> Path:  # type: ignore[no-untyped-def]
    """pytest keeps only its last few temp folders: save what's needed to debug a failed run."""
    folder = REPO_ROOT / "test-artifacts" / f"web-e2e-{time.strftime('%Y%m%d-%H%M%S')}"
    folder.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(folder / "page.png"), full_page=True)
    (folder / "chat.txt").write_text(page.inner_text("main")[-20_000:], encoding="utf-8")
    events = workspace.forge_dir / "transcripts" / "events.jsonl"
    if events.exists():
        (folder / "events.jsonl").write_bytes(events.read_bytes())
    for name in ("state.json", "PLAN.md", "PROGRESS.md"):
        if (workspace.forge_dir / name).exists():
            (folder / name).write_bytes((workspace.forge_dir / name).read_bytes())
    return folder


def test_requirement_through_the_web_ui(server: ServerSecurity, workspace: Workspace) -> None:
    with playwright_api.sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_context(accept_downloads=True).new_page()
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
        box.fill(REQUIREMENT)
        page.keyboard.press("Enter")

        deadline = time.monotonic() + RUN_TIMEOUT_S
        reloaded = False
        idle_since: float | None = None
        replies = 0
        while time.monotonic() < deadline:
            clicked = answer_waiting_cards(page)
            text = page.inner_text("main")
            # Forge sometimes asks in plain chat text and waits: reply like a user would (in the composer).
            state = page.evaluate("() => fetch('/api/state').then(r => r.json())")
            idle = not state.get("busy") and not page.query_selector("[data-card][data-pending]")
            idle_since = (idle_since or time.monotonic()) if idle and not clicked else None
            if idle_since and time.monotonic() - idle_since > 20 and replies < 4 and "Done:" not in text:
                box.fill(USER_REPLY)
                page.keyboard.press("Enter")
                replies += 1
                idle_since = None
            if not reloaded and page.query_selector("[data-card=approval]:not([data-pending])"):
                page.reload()  # mid-run: the chat is rebuilt from the event log
                page.wait_for_selector("[data-card=approval]:not([data-pending])", timeout=30_000)
                assert REQUIREMENT[:40] in page.inner_text("main")
                reloaded = True
            if "Done:" in text and "COPY_INSTRUCTIONS" in text:
                break
            time.sleep(2)
        else:
            pytest.fail(
                f"the run did not finish through the web UI; evidence in {keep_evidence(page, workspace)}"
            )

        assert reloaded
        page.click("[role=tab]:has-text('Tasks')")
        page.wait_for_selector("[role=tabpanel] span:text-is('done')")
        assert not page.query_selector("[role=tabpanel] span:text-is('pending')")
        page.click("[role=tab]:has-text('Diffs')")
        page.wait_for_selector(".d2h-wrapper")
        assert "claims" in page.inner_text("[role=tabpanel]").lower()
        page.click("[role=tab]:has-text('Files')")
        with page.expect_download() as download:
            page.click("text=Download output")
        archive = zipfile.ZipFile(io.BytesIO(Path(download.value.path()).read_bytes()))
        assert "COPY_INSTRUCTIONS.md" in archive.namelist()
        assert any(name.startswith("backend/claims_app/") for name in archive.namelist())

        # Stop: a change request is interrupted.
        box.fill("Also add the count to the policy detail response.")
        page.keyboard.press("Enter")
        page.wait_for_selector("button:has-text('Stop')", timeout=60_000)
        page.click("button:has-text('Stop')")
        page.wait_for_selector("text=Interrupted", timeout=60_000)
        assert problems == [], problems
        browser.close()
