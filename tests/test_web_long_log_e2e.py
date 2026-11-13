"""CV3 in headless Edge: a project whose log holds 20,000 events opens fast because the chat draws only the latest
items and a "Show earlier" button adds more (D-593, D-594). The time is printed; before the window it was 10.5 s."""

from __future__ import annotations

import json
import time

import pytest

from forge.safety.server_security import ServerSecurity
from forge.workspace.workspace import Workspace
from tests.conftest import REPO_ROOT
from tests.test_web_conversations_e2e import (  # noqa: F401  (a server on the conversation paths)
    server,
    workspace,
)
from tests.test_web_e2e import configured_secrets, playwright_api  # noqa: F401

pytestmark = pytest.mark.e2e

TURNS = 5000  # four events each: 20,000 events


def write_long_log(project: Workspace) -> None:
    """The old-style log; the project copies it into conversation c1 when it is opened."""
    log = project.forge_dir / "transcripts" / "events.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as handle:
        seq = 0

        def line(kind: str, payload: dict[str, object]) -> str:
            nonlocal seq
            seq += 1
            return json.dumps(
                {"seq": seq, "type": kind, "ts": "2026-01-01T00:00:00.000+00:00", "payload": payload}
            )

        for turn in range(TURNS):
            call = f"call_{turn}"
            handle.write(line("user_message", {"text": f"question {turn}"}) + "\n")
            handle.write(
                line(
                    "tool_call_started",
                    {
                        "id": call,
                        "name": "read_file",
                        "summary": f"read file {turn}",
                        "arguments": {"path": "a.py"},
                    },
                )
                + "\n"
            )
            handle.write(
                line(
                    "tool_call_finished",
                    {
                        "id": call,
                        "name": "read_file",
                        "ok": True,
                        "summary": f"read file {turn}",
                        "preview": "ok",
                        "duration_s": 0.1,
                    },
                )
                + "\n"
            )
            handle.write(line("message_done", {"text": f"answer {turn}", "model": "gpt51"}) + "\n")


OPEN_SECONDS_LIMIT = 4.0


def test_a_project_with_twenty_thousand_events_opens_fast_and_shows_earlier_on_request(
    server: ServerSecurity,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    write_long_log(workspace)
    post = (
        "async ([path, body]) => (await fetch(path, {method: 'POST',"
        " headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})).status"
    )
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
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
        assert page.evaluate(post, ["/api/open", {"workspace": str(workspace.root)}]) == 200
        started = time.perf_counter()
        page.reload()
        page.wait_for_selector(f"text=answer {TURNS - 1}", timeout=int(OPEN_SECONDS_LIMIT * 4000))
        seconds = time.perf_counter() - started
        button = page.get_by_test_id("show-earlier")
        label = button.inner_text()
        page.screenshot(path=str(shots / "chat-long-window.png"))
        older = f"answer {TURNS - 150}"  # about 450 items from the end: outside the first window of 300
        assert page.get_by_text(older, exact=True).count() == 0
        button.click()
        page.wait_for_selector(f"text={older}", timeout=10000)
        assert button.inner_text() != label  # fewer messages are hidden now
        browser.close()
    print(f"\nOPEN of a log with {TURNS * 4} events: {seconds:.1f} s; button: {label}")
    assert not problems, problems
    assert seconds < OPEN_SECONDS_LIMIT
    assert "more" in label
