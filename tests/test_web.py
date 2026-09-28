"""M9W: the web UI server — spec §15A.6 security tests and the API/WebSocket behaviour (no model calls)."""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from forge.engine.events import EventBus
from forge.engine.session_host import SessionHost
from forge.safety.redact import Redactor
from forge.web.manager import WebSessionManager
from forge.web.security import COOKIE, BindError, ServerSecurity, check_bind_host
from forge.web.server import create_app
from forge.workspace.create import create_workspace
from forge.workspace.workspace import Workspace
from tests.helpers import mocked_router

PORT = 8799
BASE = f"http://127.0.0.1:{PORT}"
ORIGIN = {"origin": BASE}
WS_URL = f"ws://127.0.0.1:{PORT}/ws"


def unreachable(request: object) -> object:
    raise AssertionError("no LLM call expected")


def direct_session(workspace: Workspace) -> SessionHost:
    return SessionHost(mocked_router(unreachable), EventBus(redactor=Redactor()), workspace=workspace)


@pytest.fixture
def security() -> ServerSecurity:
    return ServerSecurity(port=PORT, token="test-token-0123456789")  # check_secrets: fake


@pytest.fixture
def workspace(original_repo: Path, tmp_path: Path) -> Workspace:
    return create_workspace(original_repo, tmp_path / "ws", "backend")


@pytest.fixture
def client(security: ServerSecurity, isolated_forge_home: Path) -> Iterator[TestClient]:
    manager = WebSessionManager(isolated_forge_home, direct_session)
    with TestClient(create_app(manager, security), base_url=BASE) as test_client:
        yield test_client


def login(client: TestClient, security: ServerSecurity) -> None:
    response = client.get(f"/?t={security.token}", follow_redirects=False)
    assert response.status_code == 303 and response.headers["location"] == "/"
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie.replace("Strict", "strict")


# --- security (spec §15A.6) ---


def test_requests_without_the_token_are_refused(client: TestClient, security: ServerSecurity) -> None:
    assert client.get("/").status_code == 403
    assert client.get("/api/state").status_code == 403
    assert client.get("/?t=wrong-token").status_code == 403
    assert client.get("/static/app.js").status_code == 403
    login(client, security)
    page = client.get("/")
    assert page.status_code == 200 and "<title>Forge</title>" in page.text
    assert client.cookies.get(COOKIE) == security.token


def test_foreign_origin_and_host_are_refused(client: TestClient, security: ServerSecurity) -> None:
    login(client, security)
    assert client.get("/api/state", headers={"origin": "http://evil.example"}).status_code == 403
    assert client.get("/api/state", headers={"host": "evil.example"}).status_code == 403  # DNS rebinding
    assert client.get("/api/state", headers=ORIGIN).status_code == 200


def test_strict_content_security_policy(client: TestClient, security: ServerSecurity) -> None:
    login(client, security)
    policy = client.get("/").headers["content-security-policy"]
    assert (
        "script-src 'self'" in policy
        and "unsafe-inline" not in policy
        and "http" not in policy.replace("ws://", "")
    )


def test_only_loopback_binding_is_allowed() -> None:
    for host in ("0.0.0.0", "192.168.1.5", "::", "example.com"):
        with pytest.raises(BindError):
            check_bind_host(host)
    assert check_bind_host("127.0.0.1") == "127.0.0.1"
    assert check_bind_host("localhost") == "127.0.0.1"


def test_file_endpoints_stay_in_the_workspace_and_hide_secrets(
    client: TestClient, security: ServerSecurity, workspace: Workspace
) -> None:
    login(client, security)
    assert client.post("/api/open", json={"workspace": str(workspace.root)}).status_code == 200
    readme = client.get("/api/file", params={"root": "repo", "path": "backend/README.md"})
    assert readme.status_code == 200 and readme.json()["text"]
    for path in (
        "../../outside/secret.txt",
        "..\\..\\x",
        "backend/../../.forge/workspace.json",
        "C:/Windows/win.ini",
    ):
        assert client.get("/api/file", params={"root": "repo", "path": path}).status_code in (403, 404), path
    assert client.get("/api/file", params={"root": "repo", "path": "backend/.env"}).status_code == 403
    assert client.get("/api/file", params={"root": "forge", "path": "state.json"}).status_code == 400
    names = [
        e["name"]
        for e in client.get("/api/tree", params={"root": "repo", "dir": "backend"}).json()["entries"]
    ]
    assert "claims_app" in names and "venv" not in names


# --- API ---


def test_state_diff_and_output_zip(
    client: TestClient, security: ServerSecurity, workspace: Workspace
) -> None:
    login(client, security)
    assert client.get("/api/state").json()["workspace"] is None
    client.post("/api/open", json={"workspace": str(workspace.root)})
    errors = workspace.path_of("backend/claims_app/errors.py")
    errors.write_text(errors.read_text(encoding="utf-8") + "\n# changed by the test\n", encoding="utf-8")

    state = client.get("/api/state").json()
    assert state["workspace"]["name"] == workspace.info.name and state["phase"] == "direct"
    assert state["recent"][0]["path"] == str(workspace.root)
    assert "changed by the test" in client.get("/api/diff").json()["patch"]
    tree = client.get("/api/tree", params={"root": "repo", "dir": "backend/claims_app"}).json()["entries"]
    assert {e["name"]: e["status"] for e in tree}["errors.py"] == "modified"

    archive = zipfile.ZipFile(io.BytesIO(client.get("/api/output.zip").content))
    assert "COPY_INSTRUCTIONS.md" in archive.namelist()
    assert "backend/claims_app/errors.py" in archive.namelist()
    assert all(".env" not in name for name in archive.namelist())


# --- WebSocket ---


def events_until(socket: Any, predicate: Any, limit: int = 200) -> list[dict[str, Any]]:
    seen = []
    for _ in range(limit):
        message = socket.receive_json()
        if message.get("type") == "event":
            seen.append(message["event"])
            if predicate(message["event"]):
                return seen
    raise AssertionError("expected event not received")


def test_websocket_replays_accepts_inputs_and_has_one_controller(
    client: TestClient, security: ServerSecurity, workspace: Workspace
) -> None:
    login(client, security)
    client.post("/api/open", json={"workspace": str(workspace.root)})

    with client.websocket_connect(WS_URL, headers=ORIGIN) as first:
        first.send_json({"type": "hello", "since": 0})
        hello = first.receive_json()
        assert hello["type"] == "hello" and hello["controls"] is True
        first.send_json({"type": "input", "input": {"kind": "slash_command", "text": "/help"}})
        seen = events_until(
            first, lambda e: e["type"] == "notice" and "/rewind" in e["payload"].get("text", "")
        )
        help_seq = seen[-1]["seq"]

        with client.websocket_connect(WS_URL, headers=ORIGIN) as second:
            second.send_json({"type": "hello", "since": 0})
            assert second.receive_json()["controls"] is False  # watches only
            replayed = events_until(second, lambda e: e["seq"] == help_seq)
            assert replayed[-1]["payload"]["kind"] == "command_output"  # a reconnect gets the history
            second.send_json({"type": "input", "input": {"kind": "slash_command", "text": "/help"}})
            assert second.receive_json()["type"] == "rejected"
            second.send_json({"type": "take_control"})
            assert second.receive_json() == {"type": "control", "controls": True}

        first.send_json({"type": "input", "input": {"kind": "bogus"}})
        rejected = first.receive_json()
        assert rejected["type"] == "rejected"


def test_websocket_refuses_foreign_origins(client: TestClient, security: ServerSecurity) -> None:
    login(client, security)
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect(WS_URL, headers={"origin": "http://evil.example"}) as ws,
    ):
        ws.receive_json()


def test_standalone_workspace_from_the_web_api(
    client: TestClient, security: ServerSecurity, isolated_forge_home: Path, tmp_path: Path
) -> None:
    from forge.modeb.profile import ProfileStore

    login(client, security)
    ProfileStore(isolated_forge_home).create("web-host")
    assert client.get("/api/profiles").json() == ["web-host"]
    response = client.post(
        "/api/standalone", json={"workspace": str(tmp_path / "wsb"), "profile": "web-host"}
    )
    assert response.status_code == 200, response.text
    state = client.get("/api/state").json()
    assert state["workspace"]["mode"] == "B" and state["workspace"]["repo"] == "standalone (Mode B)"
    assert (
        client.post("/api/standalone", json={"workspace": str(tmp_path / "x"), "profile": "nope"}).status_code
        == 400
    )


def test_standalone_workspace_with_a_new_profile_from_the_browser(
    client: TestClient, security: ServerSecurity, isolated_forge_home: Path, tmp_path: Path
) -> None:
    # The standalone flow without a terminal: the profile is created in the same form.
    from forge.modeb.profile import ProfileStore

    login(client, security)
    response = client.post(
        "/api/standalone",
        json={
            "workspace": str(tmp_path / "wsn"),
            "new_profile": "office-app",
            "sensitive_terms": "Acme, Zeta ",
        },
    )
    assert response.status_code == 200, response.text
    assert client.get("/api/profiles").json() == ["office-app"]
    assert ProfileStore(isolated_forge_home).open("office-app").sensitive_terms == ["Acme", "Zeta"]
    bad = client.post("/api/standalone", json={"workspace": str(tmp_path / "y"), "new_profile": "bad name!"})
    assert bad.status_code == 400 and "letters, digits" in bad.json()["detail"]
    empty = client.post("/api/standalone", json={"workspace": str(tmp_path / "z")})
    assert empty.status_code == 400 and "Choose a host profile" in empty.json()["detail"]
