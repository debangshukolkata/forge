"""The question pop-up in headless Edge (D-214): choosing only selects, the answer is sent with Submit,
the user's own answer or a note is part of it, and "Answer later" leaves the question in the chat. The model
is simulated at the network layer; the question travels the real path (ask_user -> question card -> answer
-> the model's next call)."""

from __future__ import annotations

import json
import threading
import time

import httpx2
import pytest
import uvicorn

from forge.engine.session_host import SessionHost
from forge.protocol.events import EventBus
from forge.safety.redact import Redactor
from forge.safety.server_security import ServerSecurity
from forge.web.manager import WebSessionManager
from forge.web.run import free_port
from forge.web.server import create_app
from tests.conftest import REPO_ROOT
from tests.helpers import function_call_output, mocked_router, reply, responses_body, text_output
from tests.test_web_e2e import configured_secrets, workspace  # noqa: F401  (fixtures)

pytestmark = pytest.mark.e2e
playwright_api = pytest.importorskip("playwright.sync_api")

ASK_ARGS = json.dumps(
    {
        "question": "Which database should Reading Radar use?",
        "context": "The brief does not say.",
        "options": [
            {"label": "SQLite", "description": "No setup", "pros": "Simple"},
            {"label": "Postgres", "description": "Needs a server", "risks": "More to run"},
        ],
        "recommended": "SQLite",
    }
)


@pytest.fixture
def model_requests() -> list[dict[str, object]]:
    return []


@pytest.fixture
def server(isolated_forge_home, model_requests):  # type: ignore[no-untyped-def]
    def handler(request: httpx2.Request) -> httpx2.Response:
        model_requests.append(json.loads(request.content))
        if len(model_requests) == 1:
            return reply(request, responses_body([function_call_output("ask_user", ASK_ARGS)]))
        return reply(request, responses_body([text_output("Going with the answer you gave.")]))

    port = free_port(0)
    security = ServerSecurity(port=port)
    manager = WebSessionManager(
        isolated_forge_home,
        lambda ws: SessionHost(
            mocked_router(handler),
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


def open_project_and_ask(p, server, workspace):  # type: ignore[no-untyped-def]  # noqa: F811
    try:
        browser = p.chromium.launch(channel="msedge", headless=True)
    except Exception as error:
        pytest.skip(f"headless Edge not available: {error}")
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    problems: list[str] = []
    page.on("pageerror", lambda e: problems.append(str(e)))
    page.goto(server.url())
    page.wait_for_selector("text=Start something new.")
    page.evaluate(
        "p => fetch('/api/open', {method: 'POST', headers: {'Content-Type': 'application/json'},"
        " body: JSON.stringify({workspace: p})})",
        str(workspace.root),
    )
    page.reload()
    box = page.locator("textarea[aria-label=Message]")
    box.wait_for()
    box.fill("Build Reading Radar")
    box.press("Enter")
    return browser, page, problems


def test_choosing_selects_and_the_answer_is_sent_with_submit(  # type: ignore[no-untyped-def]
    server,
    workspace,  # noqa: F811
    model_requests,
) -> None:
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        browser, page, problems = open_project_and_ask(p, server, workspace)
        dialog = page.locator("[role=dialog][aria-label='Question from Forge']")
        dialog.wait_for()
        assert "Which database should Reading Radar use?" in dialog.inner_text()
        submit = dialog.locator("button:has-text('Submit answer')")
        summary = dialog.locator("[data-testid=question-summary]")
        assert submit.is_disabled() and "Choose an option" in summary.inner_text()

        dialog.locator("[role=radio]:has-text('Postgres')").click()
        assert dialog.is_visible() and len(model_requests) == 1  # a click only selects: nothing was sent
        assert "Your answer: Postgres" in summary.inner_text() and not submit.is_disabled()

        dialog.locator("[role=radio]:has-text('SQLite')").click()  # change of mind
        assert dialog.locator("[role=radio][aria-checked=true]").count() == 1
        dialog.locator("textarea[aria-label='Your own answer or a note']").fill("keep it simple")
        assert "SQLite" in summary.inner_text() and "keep it simple" in summary.inner_text()
        page.screenshot(path=str(shots / "question-popup-light.png"))

        submit.click()
        dialog.wait_for(state="hidden")
        page.wait_for_selector("text=Going with the answer you gave.")
        page.wait_for_selector("text=You chose: SQLite (with a note)")
        browser.close()
    sent = json.dumps(model_requests[1])
    assert "The user chose: SQLite. They added: keep it simple" in sent
    assert not problems, problems


def test_own_answer_alone_and_answering_later(  # type: ignore[no-untyped-def]
    server,
    workspace,  # noqa: F811
    model_requests,
) -> None:
    with playwright_api.sync_playwright() as p:
        browser, page, problems = open_project_and_ask(p, server, workspace)
        dialog = page.locator("[role=dialog][aria-label='Question from Forge']")
        dialog.wait_for()

        dialog.locator("button[aria-label='Answer later']").click()  # the question stays, inside the chat
        dialog.wait_for(state="hidden")
        card = page.locator("[data-card=question][data-pending]")
        card.locator("[role=radio]:has-text('Postgres')").wait_for()
        card.locator("button:has-text('Show as a pop-up')").click()
        dialog.wait_for()

        dialog.locator("textarea[aria-label='Your own answer or a note']").fill("a JSON file")
        dialog.locator("button:has-text('Submit answer')").click()
        dialog.wait_for(state="hidden")
        page.wait_for_selector("text=You answered: a JSON file")
        browser.close()
    assert "The user answered: a JSON file" in json.dumps(model_requests[1])
    assert not problems, problems
