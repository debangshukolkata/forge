"""D-204 in headless Edge: the first-run settings-file guide (where the file is, what goes in it, the
template, what is filled in, the optional-tool questions) and the drawer that follows it with a test per
connection. The model call is stubbed (`forge doctor` covers it); nothing here types a key into the page."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.config import load_config
from forge.doctor import CheckResult, required_secret_names
from forge.environment import checks
from forge.safety.server_security import ServerSecurity
from tests.conftest import REPO_ROOT
from tests.test_web_e2e import configured_secrets, playwright_api, server  # noqa: F401

pytestmark = pytest.mark.e2e

KEY = "typed-azure-key-0123456789"  # check_secrets: fake
PG_PASSWORD = "pw-secret-4567"  # check_secrets: fake


def test_the_first_run_guide_and_the_drawer_after_it(
    server: ServerSecurity,  # noqa: F811
    isolated_forge_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names = required_secret_names(load_config(isolated_forge_home))
    for name in names:
        monkeypatch.delenv(name, raising=False)  # a machine that has never been set up
    for name in ("LOCAL_PG_URL", "DEV_PG_URL"):
        monkeypatch.delenv(name, raising=False)
    env_file = isolated_forge_home / ".env"
    monkeypatch.setenv("FORGE_ENV_FILE", str(env_file))

    async def answers(config: object, secrets: object) -> list[CheckResult]:
        return [CheckResult("Model gpt51", "ok", "serves gpt-5.1 via responses API in 0.4s")]

    monkeypatch.setattr(checks, "check_models", answers)
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with playwright_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        context = browser.new_context(
            viewport={"width": 1440, "height": 1300}, permissions=["clipboard-read", "clipboard-write"]
        )
        page = context.new_page()
        problems: list[str] = []
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())

        # --- the guide ---
        page.wait_for_selector("text=Set up Forge.")
        assert page.locator("[data-testid=env-path]").inner_text() == str(env_file)
        page.wait_for_selector("text=Not created yet")
        page.wait_for_selector("text=This page cannot see your keys.")
        template = page.locator("pre[aria-label=Template]").inner_text()
        assert "AZURE_OPENAI_API_KEY=<key>" in template and "LOCAL_PG_URL=postgresql://" in template
        assert "DEV_PG_URL=postgresql://" in template and "SERPAPI_API_KEY=" in template
        assert "FORGE_PG_URL" not in template
        page.wait_for_selector("h3:has-text('Forge database')")
        page.wait_for_selector("h3:has-text('Development database (read-only)')")
        assert page.locator("[data-variable=LOCAL_PG_URL]").get_attribute("data-filled") == "no"

        # Copy buttons put the template and the path on the clipboard.
        page.click("button:has-text('Copy template')")
        page.wait_for_selector("button:has-text('Copied')")
        assert page.evaluate("navigator.clipboard.readText()").replace("\r\n", "\n") == page.evaluate(
            "fetch('/api/setup').then(r => r.json()).then(j => j.template)"
        )
        page.click("button:has-text('Copy path')")
        page.wait_for_selector("button:has-text('Copied')")
        assert page.evaluate("navigator.clipboard.readText()") == str(env_file)

        # Nothing to continue with yet: the required Azure names are missing.
        assert page.locator("button:has-text('Continue to the connection tests')").is_disabled()
        assert "AZURE_OPENAI_API_KEY" in page.locator("[role=status]").inner_text()

        # The two optional tools are asked about here too, and the answers are saved.
        page.locator(
            "[role=group][aria-label='Is Tesseract installed on this computer?'] button:has-text('Yes')"
        ).click()
        page.locator("[role=group][aria-label='Is Gemini enabled for you?'] button:has-text('No')").click()
        saved = page.evaluate("fetch('/api/environment').then(r => r.json()).then(j => j.saved.answers)")
        assert saved == {"tesseract": True, "gemini": False}

        # The user edits the file themselves (the test plays the user), then asks Forge to check it.
        lines = [
            f"{name}=value-for-{name.lower()}" for name in sorted(names) if name != "AZURE_OPENAI_API_KEY"
        ]
        lines += [
            f"AZURE_OPENAI_API_KEY={KEY}",
            f"LOCAL_PG_URL=postgresql://user:{PG_PASSWORD}@127.0.0.1:1/forge_dev",
        ]
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        page.click("button:has-text('Check the file')")
        page.wait_for_selector("text=All required names are filled in.")
        assert page.locator("[data-variable=AZURE_OPENAI_API_KEY]").get_attribute("data-filled") == "yes"
        assert page.locator("[data-variable=LOCAL_PG_URL]").get_attribute("data-filled") == "yes"
        assert page.locator("[data-variable=DEV_PG_URL]").get_attribute("data-filled") == "no"
        page.wait_for_selector("text=File found")
        content = page.content() + page.inner_text("body")
        assert KEY not in content and PG_PASSWORD not in content  # the page never learns a value
        page.screenshot(path=str(shots / "setup-guide-light.png"), full_page=True)

        # --- the drawer: it reads the values and tests only when asked ---
        page.click("button:has-text('Continue to the connection tests')")
        drawer = page.locator("[role=dialog][aria-label=Environment]")
        drawer.wait_for()
        azure, local, dev = (
            drawer.locator(f"[data-check={check}]") for check in ("azure", "postgres_local", "postgres_dev")
        )
        assert "Not tested yet" in azure.inner_text() and "Not tested yet" in local.inner_text()
        assert (
            "Forge database" in local.inner_text() and "Development database (read-only)" in dev.inner_text()
        )
        assert "never writes" in dev.inner_text()

        azure.locator("button:has-text('Test')").click()
        page.wait_for_selector("[data-check=azure] >> text=Connected")
        assert (
            "Not tested yet" in local.inner_text() and "Not tested yet" in dev.inner_text()
        )  # one at a time
        local.locator("button:has-text('Test')").click()
        page.wait_for_selector("[data-check=postgres_local] >> text=Failed")  # nothing listens on that port
        assert "Not tested yet" in dev.inner_text()  # the other database is left alone
        assert PG_PASSWORD not in drawer.inner_text()
        drawer.locator("button:has-text('Test all')").click()
        page.wait_for_selector("[data-check=postgres_dev] >> text=Warning")
        assert "DEV_PG_URL is not set" in dev.inner_text()
        page.screenshot(path=str(shots / "environment-tests-light.png"))

        # The drawer links back to the guide, which can be left again.
        page.click("button:has-text('Where is the file, and what goes in it?')")
        page.wait_for_selector("text=Forge's settings file.")
        page.click("button:has-text('Back')")
        page.wait_for_selector("text=Start something new.")
        browser.close()
    assert not problems, problems
