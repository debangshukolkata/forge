"""D-603 in headless Edge: DebCraft signs in to a stand-in site with the same two clicks as the real one (Sign in, SSO
redirect with a uuid_key, a second page with Proceed, the dashboard) and keeps the token from a cookie or a header."""

from __future__ import annotations

import base64
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest
import yaml

from forge.toolkit.app_logins import TokenStore, load_logins
from forge.toolkit.base import ToolContext
from forge.tools import app_login
from forge.tools.app_login import MARKER, AppLogin, profile_dir, sign_in
from forge.workspace.create import create_workspace
from tests.test_web_e2e import configured_secrets, playwright_api  # noqa: F401

pytestmark = pytest.mark.e2e


def _jwt() -> str:
    def part(data: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    return f"{part({'alg': 'HS256'})}.{part({'sub': 'u', 'exp': time.time() + 3600})}.sig" + "x" * 20


TOKEN = _jwt()
LOGIN_PAGE = "<html><body><h1>Welcome back</h1><button onclick=\"location.href='/app/sso'\">Sign in</button></body></html>"
FORM_PAGE = (
    "<html><body><h1>Choose</h1><button onclick=\"fetch('/app/proceed', {method: 'POST'})"
    ".then(() => location.href = '/app/landing-home/dashboard')\">Proceed</button></body></html>"
)
LANDING = (
    "<html><body><h1>Dashboard</h1><script>fetch('/app/api/me', {headers: {Authorization: 'Bearer "
    + TOKEN
    + "'}})</script></body></html>"
)


class Site(BaseHTTPRequestHandler):
    api_headers: ClassVar[list[str]] = []

    def _send(self, status: int, body: str = "", headers: dict[str, str] | None = None) -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(data)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        if path == "/app/login/":
            self._send(200, LOGIN_PAGE)
        elif path == "/app/sso":
            self._send(302, headers={"Location": "/app/?uuid_key=abc&wisdom_user_exists=True"})
        elif path == "/app/":
            self._send(200, FORM_PAGE)
        elif path == "/app/landing-home/dashboard":
            self._send(200, LANDING)
        elif path == "/app/api/me":
            Site.api_headers.append(self.headers.get("Authorization", ""))
            self._send(200, "{}")
        else:
            self._send(404)

    def do_POST(self) -> None:
        if self.path == "/app/proceed":
            self._send(200, "ok", {"Set-Cookie": f"access_token_cookie={TOKEN}; Path=/"})
        else:
            self._send(404)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def site(isolated_forge_home: Path):  # type: ignore[no-untyped-def]
    server = ThreadingHTTPServer(("127.0.0.1", 0), Site)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    Site.api_headers = []
    base = f"http://127.0.0.1:{server.server_port}/app/login/"
    steps = [
        {"click": "Sign in"},
        {"wait_url": "uuid_key"},
        {"click": "Proceed"},
        {"wait_url": "landing-home"},
    ]
    environments = {
        "by_cookie": {
            "login_url": base,
            "token_name": "COOKIE_TOKEN",
            "token": {"cookie": "access_token_cookie"},
            "steps": steps,
        },
        "by_header": {
            "login_url": base,
            "token_name": "HEADER_TOKEN",
            "token": {"header": "authorization"},
            "steps": steps,
        },
        "broken": {
            "login_url": base,
            "token_name": "BROKEN_TOKEN",
            "token": {"cookie": "access_token_cookie"},
            "steps": [{"click": "A button that is not there"}],
        },
    }
    (isolated_forge_home / "app_logins.yaml").write_text(
        yaml.safe_dump({"environments": environments}), encoding="utf-8"
    )
    for name in environments:  # a profile that has signed in before: no window opens in the test
        folder = profile_dir(load_logins(isolated_forge_home)[name], isolated_forge_home)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / MARKER).write_text("signed in", encoding="utf-8")
    yield isolated_forge_home
    server.shutdown()


def _skip_without_edge(error: BaseException) -> None:
    pytest.skip(f"headless Edge not available: {error}")


async def test_the_token_is_read_from_the_cookie_after_the_two_clicks(site: Path) -> None:
    result = await sign_in(load_logins(site)["by_cookie"], site)
    if not result.ok and "No browser" in result.message:
        _skip_without_edge(RuntimeError(result.message))
    assert result.ok and result.token == TOKEN, result.message


async def test_the_token_is_read_from_the_request_header(site: Path) -> None:
    result = await sign_in(load_logins(site)["by_header"], site)
    if not result.ok and "No browser" in result.message:
        _skip_without_edge(RuntimeError(result.message))
    assert result.ok and result.token == TOKEN, result.message
    assert Site.api_headers and Site.api_headers[-1] == f"Bearer {TOKEN}"


async def test_the_tool_keeps_the_token_in_the_store_and_never_shows_it(
    site: Path, original_repo: Path, tmp_path: Path
) -> None:
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    result = await AppLogin().run(AppLogin.Args(environment="by_cookie"), context)
    if not result.ok and "No browser" in result.content:
        _skip_without_edge(RuntimeError(result.content))
    assert result.ok and "COOKIE_TOKEN" in result.content and "valid for about" in result.content
    assert TOKEN not in result.content and "uuid_key" not in result.content
    assert TokenStore(site).get("COOKIE_TOKEN") == TOKEN


async def test_a_step_that_cannot_complete_says_which_one_and_asks_for_a_visible_window(
    site: Path, monkeypatch: pytest.MonkeyPatch, original_repo: Path, tmp_path: Path
) -> None:
    monkeypatch.setattr(app_login, "STEP_SECONDS_HEADLESS", 3)
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    result = await AppLogin().run(AppLogin.Args(environment="broken"), context)
    if not result.ok and "No browser" in result.content:
        _skip_without_edge(RuntimeError(result.content))
    assert not result.ok and "Step 1" in result.content and "visible=true" in result.content
    assert "gcloud auth login" in result.content
    assert TokenStore(site).get("BROKEN_TOKEN") is None


async def test_an_unknown_environment_lists_the_known_ones(
    site: Path, original_repo: Path, tmp_path: Path
) -> None:
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    result = await AppLogin().run(AppLogin.Args(environment="prod"), context)
    assert not result.ok and "by_cookie" in result.content and "by_header" in result.content
