"""Chat layout in headless Edge (D-507): the column follows the side panel, a wide table scrolls inside itself, the newest prompt stays
pinned while its reply scrolls, a file path in chat opens a card with its absolute location, and the Chat / Run map tabs are gone.
Screenshots go to test-artifacts/react-ui/."""

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

LONG_PATH = "core_features/agents_api/react_agent/service/hook_execution_service_with_a_long_name.py"
REPLY = (
    "Copy these files:\n\n| Copy? | File | Path | Why |\n|---|---|---|---|\n"
    f"| Yes | `README.md` | `backend/README.md` | `{LONG_PATH}` adds the hook runner and wires the middleware into that path |\n\n"
    + "\n\n".join(
        f"Paragraph {n}: " + "the reply keeps going so the chat has to scroll. " * 8 for n in range(14)
    )
)


def test_chat_layout_follows_the_panel_pins_the_prompt_and_shows_paths(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        browser, page = open_in_edge(p, live_server, workspace)
        live_server.publish(EventType.USER_MESSAGE, {"text": "First question about the repository"})
        live_server.publish(EventType.MESSAGE_DONE, {"text": "A short first answer."})
        live_server.publish(EventType.USER_MESSAGE, {"text": "Tell me the files I have to copy"})
        live_server.publish(EventType.MESSAGE_DONE, {"text": REPLY})
        page.wait_for_selector("text=Paragraph 13")

        assert page.locator("[role=tab]:has-text('Run map')").count() == 0
        assert page.locator("[role=tab]:has-text('Chat')").count() == 0

        # Column width follows the side panel.
        column = page.locator("[aria-live=polite] > div").first
        open_width = column.bounding_box()["width"]  # type: ignore[index]
        page.click("button[aria-label='Hide the side panel']")
        page.wait_for_timeout(300)
        closed_width = column.bounding_box()["width"]  # type: ignore[index]
        assert closed_width > open_width + 100, (open_width, closed_width)
        page.screenshot(path=str(shots / "chat-wide-panel-closed.png"))
        page.click("button[aria-label='Show the side panel']")
        page.wait_for_timeout(300)

        # No sideways scrollbar in the chat, and a table too wide for the column scrolls inside itself.
        scroller = page.locator("[aria-live=polite]").first
        sizes = scroller.evaluate("e => [e.scrollWidth, e.clientWidth]")
        assert sizes[0] <= sizes[1] + 1, sizes

        # The newest prompt stays at the top of the chat while its reply is read.
        scroller.evaluate("e => { e.scrollTop = e.scrollHeight / 2; }")
        page.wait_for_timeout(200)
        top = scroller.bounding_box()["y"]  # type: ignore[index]
        pinned = page.locator("text=Tell me the files I have to copy").first.bounding_box()
        assert pinned is not None and abs(pinned["y"] - top) < 60, (pinned, top)
        page.screenshot(path=str(shots / "chat-pinned-prompt.png"))

        # A file path opens the card with its absolute places.
        scroller.evaluate("e => { e.scrollTop = 0; }")
        page.click("code.md-file:has-text('backend/README.md')")
        page.wait_for_selector(".file-location")
        card = page.inner_text(".file-location")
        assert "Workspace copy" in card and "README.md" in card, card
        page.screenshot(path=str(shots / "chat-file-path-card.png"))
        assert page.problems == [], page.problems  # type: ignore[attr-defined]
        browser.close()
