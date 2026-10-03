"""D-129 in headless Edge: the Contracts tab of a Standalone project (pin, revise, forget) and its absence
in a repository project."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.modeb.profile import ProfileStore
from forge.safety.server_security import ServerSecurity
from forge.workspace.workspace import Workspace
from tests.conftest import REPO_ROOT
from tests.test_web_e2e import configured_secrets, playwright_api, server, workspace  # noqa: F401

pytestmark = pytest.mark.e2e

SIGNATURE = "def call_llm(prompt: str, **kwargs) -> LLMResponse"


def test_contracts_tab(
    server: ServerSecurity,  # noqa: F811
    workspace: Workspace,  # noqa: F811
    isolated_forge_home: Path,
    tmp_path: Path,
) -> None:
    ProfileStore(isolated_forge_home).create("web-host")
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    post = (
        "async ([path, body]) => (await fetch(path, {method: 'POST',"
        " headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})).status"
    )
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        problems: list[str] = []
        # the invalid seam below is refused with a 400 on purpose; the browser logs that
        page.on(
            "console",
            lambda m: problems.append(m.text) if m.type == "error" and "400" not in m.text else None,
        )
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Start something new.")

        # A repository project has no Contracts tab.
        assert page.evaluate(post, ["/api/open", {"workspace": str(workspace.root)}]) == 200
        page.reload()
        page.wait_for_selector("[role=tab]:has-text('Tasks')")
        assert page.locator("[role=tab]:has-text('Contracts')").count() == 0

        # A Standalone project has one.
        status = page.evaluate(
            post, ["/api/standalone", {"workspace": str(tmp_path / "wsb"), "profile": "web-host"}]
        )
        assert status == 200
        page.reload()
        page.click("[role=tab]:has-text('Contracts')")
        page.wait_for_selector("text=Nothing pinned yet")
        pin = page.locator("button:has-text('Pin contract')")
        assert pin.is_disabled()
        page.fill("input[placeholder=llm_call_wrapper]", "llm_call_wrapper")
        page.fill("textarea[placeholder^='def call_llm']", SIGNATURE)
        page.fill("label:has-text('Note') input", "used everywhere")
        pin.click()
        card = page.locator("[data-contract=llm_call_wrapper]")
        card.wait_for()
        assert SIGNATURE in card.inner_text() and "used everywhere" in card.inner_text()
        assert "Pinned by you" in card.inner_text()
        page.screenshot(path=str(shots / "contracts-light.png"))

        # Revise: the seam is locked, saving keeps one contract and marks it revised.
        card.locator("button:has-text('Revise')").click()
        page.wait_for_selector("h3:has-text('Revise llm_call_wrapper')")
        assert page.locator("input[placeholder=llm_call_wrapper]").get_attribute("readonly") is not None
        page.fill("textarea[placeholder^='def call_llm']", SIGNATURE + " | None")
        page.click("button:has-text('Save revision')")
        page.wait_for_selector("[data-contract=llm_call_wrapper]:has-text('| None')")
        assert page.locator("[data-contract]").count() == 1
        assert "revised" in card.inner_text()

        # An invalid seam name is explained, not swallowed.
        page.fill("input[placeholder=llm_call_wrapper]", "Not A Seam")
        page.fill("textarea[placeholder^='def call_llm']", "def x()")
        page.click("button:has-text('Pin contract')")
        page.wait_for_selector("[role=alert]:has-text('lowercase')")

        # Forget asks first.
        card.locator("button:has-text('Forget')").click()
        page.wait_for_selector("text=Forget it?")
        card.locator("button:has-text('Keep')").click()
        assert page.locator("[data-contract]").count() == 1
        card.locator("button:has-text('Forget')").click()
        card.locator("button:has-text('Forget')").last.click()
        page.wait_for_selector("text=Nothing pinned yet")
        browser.close()
    assert not problems, problems
