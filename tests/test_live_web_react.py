"""Live: a real Forge session (real model) driven entirely through the React UI in headless Edge — New project
form (standalone), an attached signature file, the requirement, and every approval / question / permission card
clicked like a user accepting the recommendations — until Forge finishes and delivers output/.
Run with: pytest -m live tests/test_live_web_react.py"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import uvicorn

from forge.config import load_secrets
from forge.session import build_session
from forge.web.manager import WebSessionManager
from forge.web.run import free_port
from forge.web.security import ServerSecurity
from forge.web.server import create_app
from tests.conftest import REPO_ROOT

pytestmark = pytest.mark.live
playwright_api = pytest.importorskip("playwright.sync_api")

REQUIREMENT = (
    "Write payments/security/masking.py with exactly the signature in the attached file. mask_pan returns the PAN "
    "with all but the last `visible` digits replaced by mask_char, keeping spaces and dashes in place, and raises "
    "ValueError for fewer than 12 or more than 19 digits. After masking it calls the host's existing "
    "payments.audit.log_event('pan_masked', digits=<number of digits>) — never with the PAN. Tests with pytest."
)
SIGNATURE = (
    'def mask_pan(pan: str, visible: int = 4, mask_char: str = "*") -> str: ...\n\n'
    "# existing in the host: payments/audit.py\n"
    "def log_event(event: str, **fields: object) -> None: ...\n"
)
RUN_LIMIT_S = 45 * 60
USER_REPLY = "Use your recommended option for every open question, note the assumptions, and continue."


@pytest.fixture
def server(isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[ServerSecurity]:
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    monkeypatch.delenv("FORGE_SKIP_TEST_RUNNER_INSTALL")  # a real project gets pytest installed
    if not load_secrets(isolated_forge_home).get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    port = free_port(8797)
    security = ServerSecurity(port=port)
    manager = WebSessionManager(
        isolated_forge_home, lambda ws: build_session(workspace=ws, orchestrated=True)
    )
    uv = uvicorn.Server(
        uvicorn.Config(
            create_app(manager, security),
            host="127.0.0.1",
            port=port,
            log_level="warning",
            ws="websockets-sansio",
        )
    )
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
        else:  # a step on the user's machine: this test can't do it
            button = card.query_selector('button:has-text("I can\'t")')
        if button is not None and button.is_enabled():
            button.click()
            clicked += 1
    return clicked


def test_a_requirement_through_the_react_ui(server: ServerSecurity, tmp_path: Path) -> None:
    signature = tmp_path / "signature.py"
    signature.write_text(SIGNATURE, encoding="utf-8")
    project = tmp_path / "payments-masking"
    evidence = REPO_ROOT / "test-artifacts" / f"react-live-{time.strftime('%Y%m%d-%H%M%S')}"
    with playwright_api.sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        problems: list[str] = []
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Start a project")
        page.fill("input[placeholder='e.g. payments-masking']", "Payments Masking")
        page.fill("input[placeholder^='C:']", str(project))
        page.click("button:has-text('Create and open')")
        box = page.locator("textarea[aria-label=Message]")
        box.wait_for(timeout=10 * 60 * 1000)  # the project's Python environment + pytest are set up first
        page.set_input_files("input[type=file]", str(signature))
        page.wait_for_selector("span[title^='.forge/inputs/']")
        box.fill(REQUIREMENT)
        page.keyboard.press("Enter")

        deadline = time.monotonic() + RUN_LIMIT_S
        done = False
        idle_polls = 0
        while time.monotonic() < deadline:
            clicked = answer_waiting_cards(page)
            state = page.evaluate("() => fetch('/api/state').then(r => r.json())")
            if state.get("phase") in ("done", "handoff") and not state.get("busy"):
                done = True
                break
            # Forge sometimes asks in plain text (no card) and goes idle: reply like a user would.
            idle_polls = (
                idle_polls + 1 if not state.get("busy") and not clicked and not state.get("pending") else 0
            )
            if idle_polls >= 3:
                box.fill(USER_REPLY)
                page.keyboard.press("Enter")
                idle_polls = 0
            time.sleep(5)
        evidence.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(evidence / "final.png"), full_page=True)
        browser.close()
    assert done, f"Forge didn't finish in {RUN_LIMIT_S // 60} minutes; see {evidence}"
    assert not problems, problems
    masking = project / "output" / "payments" / "security" / "masking.py"
    assert masking.exists(), sorted(str(p) for p in (project / "output").rglob("*"))
    source = masking.read_text(encoding="utf-8")
    assert 'def mask_pan(pan: str, visible: int = 4, mask_char: str = "*") -> str' in source
    assert "log_event" in source
    assert not (project / "output" / "payments" / "audit.py").exists()  # the host's helper is never delivered
