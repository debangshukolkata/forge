"""D-184/D-185 in headless Edge: the landing flow (create account, sign out, sign in, hub, project list, new
project form) in light and dark, with screenshots in test-artifacts/react-ui/ to look at. No model calls."""

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
from forge.web.accounts import AccountStore
from forge.web.manager import WebSessionManager
from forge.web.run import free_port
from forge.web.server import create_app
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT
from tests.helpers import mocked_router

pytestmark = pytest.mark.e2e
playwright_api = pytest.importorskip("playwright.sync_api")
PASSWORD = "correct horse battery"  # check_secrets: fake


def unreachable(request: object) -> object:
    raise AssertionError("no LLM call expected")


@pytest.fixture(autouse=True)
def configured_secrets(isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in required_secret_names(load_config(isolated_forge_home)):
        monkeypatch.setenv(name, "https://fake.invalid")  # check_secrets: fake


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
    app = create_app(manager, security, accounts=AccountStore(isolated_forge_home))
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", ws="websockets-sansio")
    uv = uvicorn.Server(config)
    thread = threading.Thread(target=uv.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not uv.started and time.monotonic() < deadline:
        time.sleep(0.05)
    yield security
    uv.should_exit = True
    thread.join(timeout=10)


def test_landing_flow_in_edge(server: ServerSecurity, original_repo: Path, tmp_path: Path) -> None:
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
        problems: list[str] = []
        page.on(
            "console",
            lambda m: problems.append(m.text) if m.type == "error" and "401" not in m.text else None,
        )
        page.on("pageerror", lambda e: problems.append(str(e)))

        # First run: create the account.
        page.goto(server.url())
        page.wait_for_selector("text=Welcome to Forge.")
        page.screenshot(path=str(shots / "login-create.png"))
        page.fill("input[autocomplete=username]", "asha")
        page.fill("label:has-text('Password') input", PASSWORD)
        page.fill("label:has-text('Repeat the password') input", "something else entirely")
        page.click("button:has-text('Create account')")
        page.wait_for_selector("text=The two passwords don't match.")
        page.fill("label:has-text('Repeat the password') input", PASSWORD)
        page.click("button:has-text('Create account')")
        page.wait_for_selector("text=Start something new.")
        page.screenshot(path=str(shots / "hub-light.png"))

        # Sign out, wrong password, then in.
        page.click("button:has-text('Sign out')")
        page.wait_for_selector("text=Sign in to Forge.")
        page.screenshot(path=str(shots / "login-signin.png"))
        page.fill("input[autocomplete=username]", "asha")
        page.fill("input[type=password]", "wrong password")
        page.click("button:has-text('Sign in')")
        page.wait_for_selector("text=The user ID or password is wrong.")
        page.fill("input[type=password]", PASSWORD)
        page.click("button:has-text('Sign in')")
        page.wait_for_selector("text=Start something new.")
        assert page.locator("button:has-text('Open a project')").is_disabled()  # nothing to open yet

        # The state survives a reload (the session cookie), and the API refuses an unsigned request.
        page.reload()
        page.wait_for_selector("text=Start something new.")

        # New project form, then the project appears in the list.
        page.click("button:has-text('New project')")
        page.wait_for_selector("text=Create and open")
        page.screenshot(path=str(shots / "new-project-light.png"))
        page.fill("input[placeholder='e.g. payments-masking']", "Payments Masking")
        page.fill("input[placeholder*='payments-masking'][placeholder^='C:']", str(tmp_path / "pm"))
        page.click("button:has-text('Create and open')")
        page.wait_for_selector("textarea[aria-label=Message]")
        page.wait_for_selector("text=What are we building?")  # the chat opens with the welcome (D-186)
        page.wait_for_timeout(500)
        page.screenshot(path=str(shots / "chat-welcome-light.png"))
        page.click("button:has-text('Write a small API with tests')")
        assert page.input_value("textarea[aria-label=Message]") == "Write a small API with tests"
        page.fill("textarea[aria-label=Message]", "/help")
        page.keyboard.press("Enter")
        page.wait_for_selector("pre:has-text('/rewind')")
        page.screenshot(path=str(shots / "chat-after-login-light.png"))

        page.click("button:has-text('Home')")
        page.wait_for_selector("text=Pick up where you left off.")
        page.click("button:has-text('Open a project')")
        page.wait_for_selector("text=Your projects.")
        page.wait_for_selector("button:has-text('Payments Masking')")
        page.screenshot(path=str(shots / "projects-light.png"))
        page.fill("input[aria-label='Search projects']", "zzz-nothing")
        page.wait_for_selector("text=No match")
        page.fill("input[aria-label='Search projects']", "payments")
        page.click("button:has-text('Payments Masking')")
        page.wait_for_selector("textarea[aria-label=Message]")
        page.wait_for_selector("pre:has-text('/rewind')")  # the earlier conversation is replayed

        # Dark theme on the landing screens.
        page.click("button[aria-label='Dark theme']")
        page.click("button:has-text('Home')")
        page.wait_for_selector("text=Start something new.")
        page.wait_for_timeout(400)
        page.screenshot(path=str(shots / "hub-dark.png"))
        page.click("button:has-text('Sign out')")
        page.wait_for_selector("text=Sign in to Forge.")
        page.screenshot(path=str(shots / "login-dark.png"))
        browser.close()
    assert not problems, problems


def test_unsigned_api_is_refused_in_the_browser(
    server: ServerSecurity, original_repo: Path, tmp_path: Path
) -> None:
    create_workspace(original_repo, tmp_path / "ws", "backend")
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context().new_page()
        page.goto(server.url())
        page.wait_for_selector("text=Welcome to Forge.")
        status = page.evaluate("fetch('/api/state').then(r => r.status)")
        assert status == 401
        browser.close()


def test_environment_screen_in_edge(
    server: ServerSecurity, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The setup screen (D-186): live rows, the model plan, confirm, and the saved result shown next time.
    The model connectivity call itself is stubbed (`forge doctor` and the live tests cover it); this tests
    what the screen does with one working and one unreachable model."""
    from forge.doctor import CheckResult
    from forge.environment import checks, store

    async def answers(config: object, secrets: object) -> list[CheckResult]:
        return [
            CheckResult("Model gpt41", "fail", "no answer from the deployment"),
            CheckResult("Model gpt51", "ok", "serves gpt-5.1 via responses API in 0.4s"),
        ]

    monkeypatch.setattr(checks, "check_models", answers)
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1500, "height": 950}).new_page()
        problems: list[str] = []
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Welcome to Forge.")
        page.fill("input[autocomplete=username]", "asha")
        page.fill("label:has-text('Password') input", PASSWORD)
        page.fill("label:has-text('Repeat the password') input", PASSWORD)
        page.click("button:has-text('Create account')")
        page.wait_for_selector("text=Start something new.")

        page.click("button:has-text('Environment')")
        drawer = page.locator("[role=dialog][aria-label=Environment]")
        drawer.wait_for()
        page.wait_for_selector(
            "[data-check=azure] >> text=Not tested yet"
        )  # opening the drawer tests nothing
        drawer.locator("button:has-text('Test all')").click()
        page.wait_for_selector("text=Azure OpenAI")
        page.wait_for_selector("text=no answer from the deployment")  # the azure row finished
        page.wait_for_selector("text=Tesseract OCR")
        page.wait_for_selector("text=gpt-5.1 >> nth=0")
        reviewer = page.locator("select[aria-label='Model for reviewer']")
        reviewer.wait_for()
        assert reviewer.input_value() == "gpt51"  # gpt41 did not answer, so the reviewer moved to gpt51
        page.wait_for_selector("text=is not answering; using gpt51 instead")
        page.wait_for_timeout(500)
        page.screenshot(path=str(shots / "environment-drawer-light.png"))

        page.click("button:has-text('Save models')")
        drawer.wait_for(state="hidden")
        saved = store.load(isolated_forge_home)
        assert saved["plan"]["reviewer"] == "gpt51" and saved["confirmed_at"]
        assert saved["results"]["azure"]["models"] == {"gpt41": False, "gpt51": True}

        # Next time the saved plan is what the drawer shows.
        page.click("button:has-text('Environment')")
        page.wait_for_selector("select[aria-label='Model for reviewer']")
        assert page.locator("select[aria-label='Model for reviewer']").input_value() == "gpt51"
        page.click("button[aria-label='Close']")
        drawer.wait_for(state="hidden")

        # The New project screen opens the drawer by itself, beside the form.
        page.click("button:has-text('Home')")
        page.click("button:has-text('New project')")
        drawer.wait_for()
        page.wait_for_selector("text=Project folder")
        page.wait_for_selector("text=no answer from the deployment")
        page.wait_for_timeout(500)
        page.screenshot(path=str(shots / "new-project-drawer-light.png"))
        page.click("button[aria-label='Dark theme']")
        page.wait_for_timeout(500)
        page.screenshot(path=str(shots / "new-project-drawer-dark.png"))
        browser.close()
    assert not problems, problems


def test_account_screen_in_edge(server: ServerSecurity) -> None:
    """D-184: change the password from the account screen; the old one stops working, the new one signs in."""
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    new_password = "a brand new passphrase"  # check_secrets: fake
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
        problems: list[str] = []
        # the wrong-password step below is refused with a 400 on purpose; the browser logs that
        page.on(
            "console", lambda m: problems.append(m.text) if m.type == "error" and "40" not in m.text else None
        )
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Welcome to Forge.")
        page.fill("input[autocomplete=username]", "asha")
        page.fill("label:has-text('Password') input", PASSWORD)
        page.fill("label:has-text('Repeat the password') input", PASSWORD)
        page.click("button:has-text('Create account')")
        page.wait_for_selector("text=Start something new.")

        page.click("button[title='Your account and password']")
        page.wait_for_selector("text=Your account.")
        page.wait_for_selector("text=Signed in as")
        change = page.locator("button:has-text('Change password')")
        assert change.is_disabled()
        page.fill("label:has-text('Current password') input", "not my password")
        page.fill("label:has-text('New password') input", new_password)
        page.fill("label:has-text('Repeat the new password') input", "something else entirely")
        change.click()
        page.wait_for_selector("text=The two new passwords don't match.")
        page.fill("label:has-text('Repeat the new password') input", new_password)
        change.click()
        page.wait_for_selector("text=The current password is wrong.")

        page.fill("label:has-text('Current password') input", PASSWORD)
        page.fill("label:has-text('New password') input", new_password)
        page.fill("label:has-text('Repeat the new password') input", new_password)
        change.click()
        page.wait_for_selector("[role=status]:has-text('Password changed.')")
        page.screenshot(path=str(shots / "account-light.png"))

        # Still signed in here; after signing out only the new password works.
        page.click("button:has-text('Back')")
        page.wait_for_selector("text=Start something new.")
        page.click("button:has-text('Sign out')")
        page.wait_for_selector("text=Sign in to Forge.")
        page.fill("input[autocomplete=username]", "asha")
        page.fill("input[type=password]", PASSWORD)
        page.click("button:has-text('Sign in')")
        page.wait_for_selector("text=The user ID or password is wrong.")
        page.fill("input[type=password]", new_password)
        page.click("button:has-text('Sign in')")
        page.wait_for_selector("text=Start something new.")
        browser.close()
    assert not problems, problems


def test_optional_tools_are_asked_before_they_are_tested(
    server: ServerSecurity, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-201: the drawer asks whether Tesseract is installed and Gemini is enabled; only a yes starts a
    test, the answer is remembered, and the server holds to it even if a page asks for the test anyway."""
    from forge.doctor import CheckResult
    from forge.environment import checks

    calls: list[str] = []

    async def answers(config: object, secrets: object) -> list[CheckResult]:
        return [CheckResult("Model gpt51", "ok", "serves gpt-5.1 via responses API in 0.4s")]

    def fake_tesseract() -> checks.Outcome:
        calls.append("tesseract")
        return checks.Outcome("tesseract", "ok", "tesseract v5.4.0 read a test image correctly (fake)")

    gemini_outcome = [checks.Outcome("gemini", "ok", "Credentials found (fake).")]

    def fake_gemini(config: object) -> checks.Outcome:
        calls.append("gemini")
        return gemini_outcome[0]

    tavily_outcome = [checks.Outcome("tavily", "ok", "The search service answered (1 result).")]

    def fake_tavily(config: object) -> checks.Outcome:
        calls.append("tavily")
        return tavily_outcome[0]

    monkeypatch.setattr(checks, "check_tavily", fake_tavily)
    monkeypatch.setattr(checks, "check_models", answers)
    monkeypatch.setattr(checks, "check_tesseract", fake_tesseract)
    monkeypatch.setattr(checks, "check_gemini", fake_gemini)
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1440, "height": 1100}).new_page()
        problems: list[str] = []
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Welcome to Forge.")
        page.fill("input[autocomplete=username]", "asha")
        page.fill("label:has-text('Password') input", PASSWORD)
        page.fill("label:has-text('Repeat the password') input", PASSWORD)
        page.click("button:has-text('Create account')")
        page.wait_for_selector("text=Start something new.")
        page.click("button:has-text('Environment')")
        drawer = page.locator("[role=dialog][aria-label=Environment]")
        drawer.wait_for()
        assert calls == []  # opening the drawer tests nothing
        drawer.locator("button:has-text('Test all')").click()
        page.wait_for_selector("text=serves gpt-5.1")

        tesseract = drawer.locator("[role=group][aria-label='Is Tesseract installed on this computer?']")
        gemini = drawer.locator("[role=group][aria-label='Is Gemini enabled for you?']")
        tesseract.wait_for()
        assert drawer.locator("text=Answer the question to test it.").count() == 3
        assert calls == []  # nothing is tested until the user says yes

        tesseract.locator("button:has-text('Yes')").click()
        page.wait_for_selector("text=read a test image correctly")
        assert calls == ["tesseract"]
        gemini.locator("button:has-text('No')").click()
        page.wait_for_selector("text=Not in use.")
        assert calls == ["tesseract"]
        page.screenshot(path=str(shots / "environment-ask-light.png"))

        # The answers are remembered: after a reload the drawer shows them and the last results, tests
        # nothing, and "Test all" then tests only what was a yes.
        page.reload()
        page.click("button:has-text('Environment')")
        tesseract.wait_for()
        assert tesseract.locator("button:has-text('Yes')").get_attribute("aria-pressed") == "true"
        assert gemini.locator("button:has-text('No')").get_attribute("aria-pressed") == "true"
        page.wait_for_selector("text=read a test image correctly")  # the saved result, not a new test
        assert calls == ["tesseract"] and "Not in use." in drawer.inner_text()
        drawer.locator("button:has-text('Test all')").click()
        for _ in range(100):
            if len(calls) >= 2:
                break
            page.wait_for_timeout(100)
        assert calls == ["tesseract", "tesseract"]  # Gemini (a no) was left alone

        # The server holds to the answer whatever a page asks for.
        status = page.evaluate(
            "fetch('/api/environment/check/gemini', {method: 'POST'})"
            ".then(r => r.json()).then(j => j.result.status)"
        )
        assert status == "off" and "gemini" not in calls

        # When Gemini does not run on this computer, an (i) icon opens the steps to fix it.
        gemini_outcome[0] = checks.Outcome(
            "gemini", "fail", "No credentials (fake).", "See the steps.", steps=checks.GEMINI_STEPS
        )
        gemini.locator("button:has-text('Yes')").click()
        page.wait_for_selector("text=No credentials (fake).")
        assert drawer.locator("[data-testid=steps]").count() == 0
        drawer.locator("button[aria-label='How to fix Gemini']").click()
        assert "gcloud auth application-default login" in drawer.locator("[data-testid=steps]").inner_text()
        page.screenshot(path=str(shots / "environment-gemini-steps-light.png"))

        # The Tavily service: when it does not work, an (i) icon says what goes in the .env file.
        tavily = drawer.locator(
            "[role=group][aria-label='Is the Tavily web search service available to you?']"
        )
        tavily_outcome[0] = checks.Outcome(
            "tavily",
            "fail",
            "The platform rejected the bearer token (fake).",
            "Fresh token.",
            steps=checks.TAVILY_STEPS,
        )
        tavily.locator("button:has-text('Yes')").click()
        page.wait_for_selector("text=rejected the bearer token (fake).")
        drawer.locator("button[aria-label='How to fix Tavily web search']").click()
        assert "TAVILY_BEARER_TOKEN" in drawer.locator("[data-check=tavily] [data-testid=steps]").inner_text()
        tavily.locator("button:has-text('No')").click()

        gemini.locator("button:has-text('No')").click()
        tesseract.locator("button:has-text('No')").click()
        page.wait_for_selector("text=Not in use. >> nth=2")
        assert drawer.locator("text=read a test image correctly").count() == 0
        browser.close()
    assert not problems, problems
