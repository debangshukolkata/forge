"""The red card (D-608): a change to the shared development database is shown in red, is not answered by a key,
and stays recognisable after it was answered."""

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

CARD = {
    "id": "Q-danger",
    "danger": True,
    "recommended": None,
    "question": "Change 1 row(s) in the shared Development database (public.agents)?",
    "context": "**This changes the shared Development database.** Other people work in it.\n\n"
    "Why DebCraft wants this: The agent stops after 5 steps; the requirement needs 20.\n\n"
    "```sql\nUPDATE public.agents SET max_steps = 20 WHERE name = 'argo'\n```\n\n"
    "**1 row(s) of `public.agents` will be changed:**\n- id=1: **max_steps** `5` → `20`\n\n"
    "DebCraft keeps the old values in this project, so the update can be set back (after another card).",
    "options": [
        {"label": "Change 1 row(s)", "description": "Exactly what is shown above, once."},
        {"label": "Do not change", "description": "Nothing is changed."},
    ],
}


def test_the_red_card_is_red_and_only_a_click_approves(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    artifacts = REPO_ROOT / "test-artifacts" / "react-ui"
    artifacts.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        browser, page = open_in_edge(p, live_server, workspace)
        live_server.publish(EventType.QUESTION_ASKED, CARD)
        page.wait_for_selector("[role=dialog][data-danger]")
        page.wait_for_selector("[data-card=question][data-danger][data-pending]")
        assert page.locator("[role=dialog] >> text=max_steps").count() >= 1
        assert page.locator("[role=dialog] [data-recommended]").count() == 0
        page.screenshot(path=str(artifacts / "danger-card-open.png"))

        # Keys neither choose nor send: "1" would pick the approving option on an ordinary question.
        page.keyboard.press("1")
        page.keyboard.press("Enter")
        assert page.locator("[role=dialog] [role=radio][aria-checked=true]").count() == 0
        assert page.locator("[role=dialog] button:has-text('Submit answer')").is_disabled()

        page.click("[role=dialog] [role=radio]:has-text('Change 1 row(s)')")
        page.wait_for_selector("[role=dialog] [data-testid=danger-submit]")
        colour = page.evaluate(
            "() => getComputedStyle(document.querySelector('[data-testid=danger-submit]')).backgroundColor"
        )
        assert colour == "rgb(215, 0, 21)", (
            colour
        )  # the theme's danger red, not the blue of an ordinary answer
        page.screenshot(path=str(artifacts / "danger-card-selected.png"))
        page.click("[role=dialog] button:has-text('Change the shared database')")
        live_server.publish(
            EventType.QUESTION_ANSWERED, {"id": "Q-danger", "choice": "Change 1 row(s)", "text": None}
        )
        page.wait_for_selector("[data-card=question][data-answered][data-danger] >> text=Approved by you")
        page.screenshot(path=str(artifacts / "danger-card-answered.png"))
        assert page.problems == []  # type: ignore[attr-defined]
        browser.close()  # type: ignore[attr-defined]
