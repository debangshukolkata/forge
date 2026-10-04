"""The approval card with a long command, in headless Edge (D-215): the title, the answer badge and the
"Always allow" button must fit without overlapping, whatever the command's length."""

from __future__ import annotations

import json

import httpx2
import pytest

from tests.conftest import REPO_ROOT
from tests.helpers import function_call_output, reply, responses_body, text_output
from tests.test_web_e2e import configured_secrets, workspace  # noqa: F401  (fixtures)
from tests.test_web_question_e2e import serve

pytestmark = pytest.mark.e2e
playwright_api = pytest.importorskip("playwright.sync_api")

LONG_SCRIPT = "scripts/a_rather_long_folder_name/another_long_folder_name/search_the_design_system_tool.py"
COMMAND = f'python {LONG_SCRIPT} "reading list personal finance calm trustworthy" --design-system'


def test_a_long_command_does_not_break_the_approval_card(isolated_forge_home, workspace) -> None:  # type: ignore[no-untyped-def]  # noqa: F811
    seen: list[dict[str, object]] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(json.loads(request.content))
        if len(seen) == 1:
            call = function_call_output("run_command", json.dumps({"command": COMMAND}))
            return reply(request, responses_body([call]))
        return reply(request, responses_body([text_output("Done.")]))

    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with serve(handler, isolated_forge_home) as server, playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1100, "height": 800}).new_page()
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
        box.fill("Run the search script")
        box.press("Enter")
        card = page.locator("[data-card=approval][data-pending]")
        card.wait_for()
        always = card.locator("[data-testid=always-allow]")
        if always.count() == 0:
            browser.close()
            pytest.skip("this command is not offered an 'Always allow' button here")
        label = always.inner_text()
        assert "Always allow" in label and always.evaluate("e => e.scrollWidth <= e.clientWidth + 1")
        assert always.bounding_box()["height"] < 60  # one line, not a tall wrapped pill

        always.click()
        badge = page.locator("[data-card=approval] [data-testid=answered-badge]")
        badge.wait_for()
        page.screenshot(path=str(shots / "approval-long-command-light.png"))
        title = page.locator("[data-card=approval] h4")
        t, b = title.bounding_box(), badge.bounding_box()
        assert t["x"] + t["width"] <= b["x"] + 1, "the answer badge overlaps the title"
        assert t["height"] < 40 and "Allow" in title.inner_text()  # the title is not squeezed into a column
        browser.close()
