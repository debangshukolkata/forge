"""D-676 in headless Edge: under each of your messages, Copy puts the whole text on the clipboard (also a long message shown
cut to three lines) and Send again puts it back in the message box. Screenshot in test-artifacts/react-ui/."""

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

PROMPT = (
    "can you run the Report Agent-1 with the prompt 'Rejection analysis dashboard. for a manufacturing org. "
    "Should take CSV as input.'\n\nline two\nline three\nline four, hidden while the message is cut"
)


def test_a_previous_prompt_is_copied_or_put_back_in_the_box(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        browser, page = open_in_edge(p, live_server, workspace)
        page.context.grant_permissions(["clipboard-read", "clipboard-write"])
        live_server.publish(EventType.USER_MESSAGE, {"text": PROMPT})
        live_server.publish(
            EventType.ERROR, {"message": "DebCraft hit an internal error (SSLError: bad record mac)."}
        )
        message = page.locator("[data-testid=user-message]").first
        message.wait_for()
        actions = message.locator("[data-testid=user-message-actions]")
        assert actions.evaluate("e => getComputedStyle(e).opacity") == "0"  # out of the way until hovered
        message.hover()
        page.wait_for_function(
            "() => getComputedStyle(document.querySelector('[data-testid=user-message-actions]')).opacity === '1'"
        )
        page.screenshot(path=str(shots / "chat-prompt-copy.png"))
        message.get_by_role("button", name="Copy message").click()
        message.get_by_role("button", name="Copied").wait_for()
        copied = page.evaluate("navigator.clipboard.readText()").replace(
            "\r\n", "\n"
        )  # Windows clipboard line ends
        assert copied == PROMPT  # the whole text, not the cut one
        message.get_by_role("button", name="Send again (puts it in the message box)").click()
        box = page.locator("textarea[aria-label=Message]")
        assert box.input_value() == PROMPT
        assert box.evaluate("e => e === document.activeElement")
        assert page.problems == [], page.problems  # type: ignore[attr-defined]
        browser.close()
