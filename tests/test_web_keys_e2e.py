"""D-200 in headless Edge: entering and replacing the Azure OpenAI values from the Environment drawer.
The model connectivity call is stubbed (`forge doctor` covers it); this tests the form, where the values go,
and that none of them comes back to the page."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.config import env_file_path, load_config
from forge.doctor import CheckResult, required_secret_names
from forge.environment import checks
from forge.safety.server_security import ServerSecurity
from tests.conftest import REPO_ROOT
from tests.test_web_e2e import configured_secrets, playwright_api, server  # noqa: F401

pytestmark = pytest.mark.e2e

KEY = "typed-azure-key-0123456789"  # check_secrets: fake
NEW_KEY = "replaced-azure-key-987654321"  # check_secrets: fake


def test_enter_and_replace_azure_values(
    server: ServerSecurity,  # noqa: F811
    isolated_forge_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in required_secret_names(load_config(isolated_forge_home)):
        monkeypatch.delenv(name, raising=False)  # nothing configured yet
    monkeypatch.delenv("FORGE_ENV_FILE", raising=False)

    async def answers(config: object, secrets: object) -> list[CheckResult]:
        return [
            CheckResult("Model gpt41", "ok", "serves gpt-4.1 via responses API in 0.3s"),
            CheckResult("Model gpt51", "ok", "serves gpt-5.1 via responses API in 0.4s"),
        ]

    monkeypatch.setattr(checks, "check_models", answers)
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1440, "height": 950}).new_page()
        problems: list[str] = []
        page.on("console", lambda m: problems.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Set up Forge")  # the first-run screen; skipped here on purpose
        page.click("button:has-text('Skip for now')")
        page.wait_for_selector("text=Start something new.")
        page.click("button:has-text('Environment')")

        form = page.locator("form[aria-label='Azure OpenAI values']")
        form.wait_for()
        assert page.locator("text=AZURE_OPENAI_API_KEY").count() >= 1
        assert form.locator("input[type=password]").count() == 1  # only the key is masked
        save = form.locator("button:has-text('Save and test')")
        assert save.is_disabled()
        for field in form.locator("input").all():
            name = field.get_attribute("aria-label") or ""
            field.fill(KEY if "KEY" in name else f"value-for-{name.lower()}")
        page.screenshot(path=str(shots / "environment-keys-light.png"))
        save.click()

        # The form goes away and the row is tested again with the new values.
        form.wait_for(state="detached")
        page.wait_for_selector("text=serves gpt-5.1")
        update = page.locator("button:has-text('Update keys')")
        update.wait_for()
        env_text = env_file_path(isolated_forge_home).read_text(encoding="utf-8")
        assert f"AZURE_OPENAI_API_KEY={KEY}" in env_text
        assert KEY not in page.content() and KEY not in page.inner_text("body")  # never shown again

        # Replacing: every required name is offered, blank fields keep what is saved.
        update.click()
        form.wait_for()
        assert form.locator("input").count() >= 3
        assert form.locator("input").first.get_attribute("placeholder") == "unchanged"
        form.locator("input[aria-label=AZURE_OPENAI_API_KEY]").fill(NEW_KEY)
        form.locator("button:has-text('Save and test')").click()
        form.wait_for(state="detached")
        env_text = env_file_path(isolated_forge_home).read_text(encoding="utf-8")
        assert f"AZURE_OPENAI_API_KEY={NEW_KEY}" in env_text and KEY not in env_text
        assert "value-for-azure_openai_endpoint" in env_text  # the field left blank kept its value

        update.click()
        form.wait_for()
        form.locator("button:has-text('Cancel')").click()
        form.wait_for(state="detached")
        browser.close()
    assert not problems, problems
