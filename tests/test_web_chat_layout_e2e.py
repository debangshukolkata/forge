"""Chat layout in headless Edge (D-507): the column follows the side panel, a table of long paths fits the column, the newest prompt stays
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
        # A table of long paths fits the column: the paths wrap after / and _ instead of pushing the last column off screen
        # (office screenshot 2026-10-29, D-549); the break points do not change the path's text.
        table = page.locator(".md table").first
        fit = table.evaluate("t => [t.scrollWidth, t.clientWidth]")
        assert fit[0] <= fit[1] + 1, fit
        assert page.locator(f"td code:has-text('{LONG_PATH[:30]}')").first.text_content() == LONG_PATH

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


def _distance_from_bottom(page: object) -> float:
    return page.locator("[aria-live=polite]").first.evaluate(  # type: ignore[attr-defined]
        "e => e.scrollHeight - e.scrollTop - e.clientHeight"
    )


def test_chat_follows_the_newest_reply_and_leaves_a_scrolled_up_reader_alone(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    """UI1: replies whose height changes after they are drawn (code blocks being highlighted, a tool card opening) must still keep the view at the bottom;
    a reader who scrolled up must not be pulled down."""
    code = (
        "```python\n"
        + "\n".join(f"value_{n} = compute_something(argument_{n}, other_{n})" for n in range(25))
        + "\n```"
    )
    reply = "\n\n".join(
        f"Paragraph {n}: " + "the reply keeps going so the chat has to scroll. " * 6 for n in range(8)
    )
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        browser, page = open_in_edge(p, live_server, workspace)
        for turn in range(3):
            live_server.publish(EventType.USER_MESSAGE, {"text": f"Question number {turn}"})
            live_server.publish(
                EventType.MESSAGE_DONE, {"text": f"{reply}\n\n{code}\n\nThe last line of answer {turn}."}
            )
            page.wait_for_selector(f"text=The last line of answer {turn}.")
            page.wait_for_timeout(600)  # highlighting and the copy buttons are added after the first draw
            assert _distance_from_bottom(page) < 40, (turn, _distance_from_bottom(page))
        page.screenshot(path=str(shots / "chat-follows-newest.png"))

        # Late growth with no new message: an image that finishes loading, a block that opens, or the activity line above the message box
        # appearing (the chat area gets shorter). The view must stay at the bottom.
        page.locator("[aria-live=polite] > div").first.evaluate(
            "e => { const d = document.createElement('div'); d.style.height = '500px'; d.textContent = 'late picture'; e.appendChild(d); }"
        )
        page.wait_for_timeout(400)
        assert _distance_from_bottom(page) < 40, ("content grew", _distance_from_bottom(page))
        page.locator("[aria-live=polite]").first.evaluate(
            "e => { e.style.height = (e.clientHeight - 120) + 'px'; e.style.flex = 'none'; }"
        )
        page.wait_for_timeout(400)
        assert _distance_from_bottom(page) < 40, ("viewport shrank", _distance_from_bottom(page))

        # A reader who scrolled up stays where they are when something new arrives.
        scroller = page.locator("[aria-live=polite]").first
        scroller.evaluate("e => { e.scrollTop = 200; }")
        page.wait_for_timeout(200)
        live_server.publish(EventType.USER_MESSAGE, {"text": "One more question"})
        live_server.publish(
            EventType.MESSAGE_DONE, {"text": f"{reply}\n\nThe last line of the final answer."}
        )
        page.wait_for_selector("text=The last line of the final answer.", state="attached")
        page.wait_for_timeout(600)
        assert scroller.evaluate("e => e.scrollTop") < 400
        assert page.problems == [], page.problems  # type: ignore[attr-defined]
        browser.close()


def test_the_jump_to_latest_button_appears_when_scrolled_up_and_takes_the_reader_back(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    """UI1 follow-up (D-521, option A): a round arrow button above the message box shows only when the reader has scrolled away from the newest message,
    carries a dot when something new arrived meanwhile, and takes the reader back to the bottom."""
    reply = "\n\n".join(
        f"Paragraph {n}: " + "the reply keeps going so the chat has to scroll. " * 6 for n in range(24)
    )
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        browser, page = open_in_edge(p, live_server, workspace)
        live_server.publish(EventType.USER_MESSAGE, {"text": "First question"})
        live_server.publish(EventType.MESSAGE_DONE, {"text": reply})
        page.wait_for_selector("text=Paragraph 23")
        page.wait_for_timeout(500)
        button = page.locator("button[title='Jump to the latest message']")
        assert button.count() == 0  # at the bottom: no button

        scroller = page.locator("[aria-live=polite]").first
        scroller.evaluate("e => { e.scrollTop = 0; }")
        page.wait_for_selector("button[title='Jump to the latest message']")
        assert (
            page.locator("button[title='Jump to the latest message'] span").count() == 0
        )  # nothing new yet: no dot

        live_server.publish(EventType.USER_MESSAGE, {"text": "Second question"})
        live_server.publish(EventType.MESSAGE_DONE, {"text": "A short answer to the second question."})
        page.wait_for_selector("button[title='Jump to the latest message'] span")  # the dot
        page.screenshot(path=str(shots / "chat-jump-to-latest.png"))

        button.click()
        page.wait_for_timeout(900)
        assert _distance_from_bottom(page) < 40, _distance_from_bottom(page)
        assert button.count() == 0
        assert page.problems == [], page.problems  # type: ignore[attr-defined]
        browser.close()


def test_the_status_line_starts_where_the_messages_start(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    """D-555, office screenshot: "Waiting for your approval" sat indented toward the middle of a wide chat column."""
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        browser, page = open_in_edge(p, live_server, workspace)
        live_server.publish(EventType.USER_MESSAGE, {"text": "can you check the file"})
        live_server.publish(EventType.MESSAGE_DONE, {"text": "I will run it to check the imports."})
        live_server.publish(
            EventType.APPROVAL_REQUESTED,
            {
                "id": "A9",
                "tool": "python_run",
                "summary": "python -c 'import x'",
                "command": "python -c 'import x'",
                "reason": "'python' is not on the allowlist",
                "can_remember_prefix": "python -c",
                "always_ask": False,
            },
        )
        status = page.locator("[role=status][aria-live=polite]:has-text('Waiting for your approval')")
        status.wait_for()
        reply = page.locator(".md:has-text('I will run it to check the imports.')").first
        for panel in ("open", "closed"):
            if panel == "closed":
                page.click("button[aria-label='Hide the side panel']")
                page.wait_for_timeout(300)
            label = status.locator("span.font-medium").first.bounding_box()
            text = reply.bounding_box()
            assert label is not None and text is not None
            assert abs(label["x"] - text["x"]) < 40, (
                panel,
                label["x"],
                text["x"],
            )  # the loader icon sits before the label
            assert status.bounding_box()["x"] <= text["x"] + 1, panel  # type: ignore[index]
        page.screenshot(path=str(shots / "chat-status-line-aligned.png"))
        browser.close()
