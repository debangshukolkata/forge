"""D-672: Gemini reports its thinking after the streamed answer; the chat must still show the answer once."""

from __future__ import annotations

import pytest

from forge.protocol.events import EventType
from forge.workspace.workspace import Workspace
from tests.conftest import REPO_ROOT
from tests.test_web_e2e import (  # noqa: F401  (the fixtures are used by name)
    LiveServer,
    configured_secrets,
    live_server,
    open_in_edge,
    playwright_api,
    workspace,
)

pytestmark = pytest.mark.e2e

ANSWER = "Only 2 lines were added to the init file of the agents."


def test_an_answer_is_shown_once_when_the_thinking_arrives_after_its_stream(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    artifacts = REPO_ROOT / "test-artifacts" / "react-ui"
    artifacts.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        _, page = open_in_edge(p, live_server, workspace)
        live_server.publish(EventType.USER_MESSAGE, {"text": "what change have you made in the init file?"})
        live_server.publish(EventType.MESSAGE_DELTA, {"text": "Only 2 lines were added "})
        live_server.publish(EventType.MESSAGE_DELTA, {"text": "to the init file of the agents."})
        page.wait_for_selector(f"text={ANSWER}")
        live_server.publish(
            EventType.THINKING_DELTA, {"text": "**Refining** I am reviewing the recent changes."}
        )
        page.wait_for_selector("text=I am reviewing the recent changes.")
        live_server.publish(
            EventType.MESSAGE_DONE,
            {"text": ANSWER, "model": "gemini4hydrogen", "usage": {"input_tokens": 10, "output_tokens": 5}},
        )
        page.wait_for_selector("text=tok")
        page.wait_for_timeout(300)
        assert page.get_by_text(ANSWER, exact=True).count() == 1
        answer_box = page.get_by_text(ANSWER, exact=True).bounding_box()
        thinking_box = page.get_by_text("I am reviewing the recent changes.").bounding_box()
        assert (
            answer_box and thinking_box and answer_box["y"] < thinking_box["y"]
        )  # the answer keeps its place
        page.screenshot(path=str(artifacts / "chat-answer-once-with-late-thinking.png"))
