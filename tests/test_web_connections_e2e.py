"""D-627 in headless Edge: the dots in the top bar and the panel behind them."""

# ruff: noqa: F811  (fixtures are imported from tests.test_web_e2e)

from __future__ import annotations

import socket
import time
from pathlib import Path

import pytest
import yaml

from forge.safety.server_security import ServerSecurity
from forge.toolkit import field_log
from forge.toolkit.app_logins import TokenStore
from tests.conftest import REPO_ROOT
from tests.test_app_logins import GOOD, jwt, write_logins
from tests.test_web_e2e import configured_secrets, server  # noqa: F401  (fixtures)

pytestmark = pytest.mark.e2e
playwright_api = pytest.importorskip("playwright.sync_api")


def test_the_top_bar_shows_a_dot_per_sign_in_and_tunnel(
    server: ServerSecurity, isolated_forge_home: Path, tmp_path: Path
) -> None:
    from forge.modeb.profile import ProfileStore

    ProfileStore(isolated_forge_home).create("dots-host")
    write_logins(isolated_forge_home, GOOD)
    TokenStore(isolated_forge_home).put("DEV_TOKEN", jwt(exp=time.time() + 42 * 60 + 30))
    field_log.write(
        "sign_in", isolated_forge_home, env="sit", ok=False, detail="the page asked for a Google login"
    )
    shots = REPO_ROOT / "test-artifacts" / "react-ui"
    shots.mkdir(parents=True, exist_ok=True)
    with socket.socket() as listener, playwright_api.sync_playwright() as p:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        (isolated_forge_home / "tunnels.yaml").write_text(
            yaml.safe_dump(
                {"tunnels": {"dev": {"command": ["gcloud", "x"], "port": listener.getsockname()[1]}}}
            ),
            encoding="utf-8",
        )
        try:
            browser = p.chromium.launch(channel="msedge", headless=True)
        except Exception as error:
            pytest.skip(f"headless Edge not available: {error}")
        page = browser.new_context(viewport={"width": 1280, "height": 800}).new_page()
        problems: list[str] = []
        page.on("pageerror", lambda e: problems.append(str(e)))
        page.goto(server.url())
        page.wait_for_selector("text=Start something new.")
        page.evaluate(
            "p => fetch('/api/standalone', {method: 'POST', headers: {'Content-Type': 'application/json'},"
            " body: JSON.stringify({workspace: p, profile: 'dots-host'})})",
            str(tmp_path / "wsd"),
        )
        page.reload()
        page.wait_for_selector("[data-testid=connections] [data-state=ok]")
        states = page.eval_on_selector_all(
            "[data-testid=connections] [data-state]",
            "all => all.map(e => e.dataset.state + ' ' + e.textContent)",
        )
        assert states == ["ok dev", "failed sit", "ok tunnel dev"], states
        page.screenshot(path=str(shots / "connections-bar-light.png"))
        page.click("[data-testid=connections]")
        page.wait_for_selector("[role=dialog][aria-label=Connections]")
        panel = page.inner_text("[role=dialog][aria-label=Connections]")
        assert "signed in, 42 min left" in panel or "signed in, 41 min left" in panel
        assert "Google login" in panel and "open on port" in panel
        assert "Sign in again" in panel and "Sign in" in panel
        page.screenshot(path=str(shots / "connections-panel-light.png"))
        page.keyboard.press("Escape")
        page.wait_for_selector("[role=dialog][aria-label=Connections]", state="detached")
        browser.close()
    assert not problems, problems
