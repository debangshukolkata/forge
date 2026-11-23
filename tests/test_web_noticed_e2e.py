"""D-641: the folded "Noticed, not changed" list, the broken start of a retried reply, and the pinned message."""

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

ANSWER = """Yes, it is possible.

**Noticed, not changed:**

- `a/constants.py:163` hard-coded secret.
  Suggestion: rotate it.
- `a/db.py:30` uses eval.

Next best step: write the models."""


def test_noticed_lists_are_folded_and_a_retried_start_goes_away(
    live_server: LiveServer,  # noqa: F811
    workspace: Workspace,  # noqa: F811
) -> None:
    artifacts = REPO_ROOT / "test-artifacts" / "react-ui"
    artifacts.mkdir(parents=True, exist_ok=True)
    risk = {"path": "b/q.py", "line": 9, "kind": "SQL built from strings", "what": "w", "advice": "x"}
    with playwright_api.sync_playwright() as p:
        _, page = open_in_edge(p, live_server, workspace)
        live_server.publish(EventType.USER_MESSAGE, {"text": "We should make a table. " * 60})
        live_server.publish(EventType.MESSAGE_DELTA, {"text": "Broken start"})
        page.wait_for_selector("text=Broken start")
        live_server.publish(EventType.NOTICE, {"kind": "retry", "text": "Model call failed; retrying"})
        page.wait_for_selector("text=Broken start", state="detached")
        live_server.publish(EventType.MESSAGE_DONE, {"text": ANSWER, "model": "m"})
        live_server.publish(
            EventType.NOTICE, {"kind": "risks_noticed", "text": "Noticed, not changed:", "risks": [risk]}
        )
        page.wait_for_function("() => document.querySelectorAll('[data-testid=noticed]').length === 2")
        folds = page.locator("[data-testid=noticed]")
        assert "Noticed, not changed · 2" in folds.nth(0).inner_text()
        assert "1 SQL built from strings" in folds.nth(1).inner_text()
        assert page.get_by_text("rotate it").count() == 0
        assert page.get_by_text("Next best step").is_visible()
        page.screenshot(path=str(artifacts / "noticed-closed.png"))
        folds.nth(0).locator("button").first.click()
        folds.nth(1).locator("button").first.click()
        assert page.get_by_text("rotate it").is_visible()
        assert "b/q.py:9" in folds.nth(1).inner_text()
        page.screenshot(path=str(artifacts / "noticed-open.png"))
        height, line, padding = page.locator("[data-testid=sticky-prompt-text]").first.evaluate(
            "e => [e.clientHeight, parseFloat(getComputedStyle(e).lineHeight), getComputedStyle(e).paddingBottom]"
        )
        assert height <= line * 3 + 2 and padding == "0px"
