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

from forge.engine.session_host import SessionHost
from forge.protocol.events import EventBus
from forge.safety.redact import Redactor
from forge.safety.server_security import BindError, ServerSecurity, check_bind_host
from forge.web.manager import WebSessionManager
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
    assert client.get("/assets/anything.js").status_code == 403
    login(client, security)
    page = client.get("/")
    assert page.status_code == 200 and "<title>Forge</title>" in page.text
    assert client.cookies.get(security.cookie_name) == security.token


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


def test_setup_reports_missing_required_secrets(
    client: TestClient, security: ServerSecurity, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FORGE_ENV_FILE", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
    login(client, security)

    status = client.get("/api/setup", headers=ORIGIN)

    assert status.status_code == 200
    assert "AZURE_OPENAI_API_KEY" in status.json()["missing"]


def test_setup_secrets_writes_the_env_file_and_never_echoes_the_value(
    client: TestClient, security: ServerSecurity, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FORGE_ENV_FILE", raising=False)
    login(client, security)
    secret = "typed-in-the-browser-0123456789"  # check_secrets: fake

    response = client.post(
        "/api/setup/secrets", headers=ORIGIN, json={"values": {"AZURE_OPENAI_API_KEY": secret}}
    )

    assert response.status_code == 200
    assert secret not in response.text
    from forge.config import env_file_path

    env_text = env_file_path(isolated_forge_home).read_text(encoding="utf-8")
    assert f"AZURE_OPENAI_API_KEY={secret}" in env_text


def test_setup_secrets_rejects_an_unrecognized_field_name(
    client: TestClient, security: ServerSecurity, isolated_forge_home: Path
) -> None:
    login(client, security)

    response = client.post(
        "/api/setup/secrets", headers=ORIGIN, json={"values": {"SOME_RANDOM_FILE_PATH": "/etc/passwd"}}
    )

    assert response.status_code == 400
    assert "SOME_RANDOM_FILE_PATH" not in (env_file_path_text(isolated_forge_home))


def env_file_path_text(home: Path) -> str:
    from forge.config import env_file_path

    path = env_file_path(home)
    return path.read_text(encoding="utf-8") if path.exists() else ""


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


def test_new_project_from_the_start_form_in_both_modes(
    client: TestClient,
    security: ServerSecurity,
    isolated_forge_home: Path,
    tmp_path: Path,
    original_repo: Path,
) -> None:
    # One form: project name + project folder in both modes, plus the existing repo in Mode A.
    from forge.modeb.profile import ProfileStore

    login(client, security)
    created = client.post(
        "/api/projects",
        json={
            "mode": "B",
            "project": "Payments Masking",
            "folder": str(tmp_path / "pm1"),
            "sensitive_terms": "Acme",
        },
    )
    assert created.status_code == 200, created.text
    state = client.get("/api/state").json()
    assert state["workspace"]["mode"] == "B" and state["recent"][0]["name"] == "Payments Masking"
    assert ProfileStore(isolated_forge_home).open("payments-masking").sensitive_terms == ["Acme"]
    again = client.post(
        "/api/projects", json={"mode": "B", "project": "payments masking", "folder": str(tmp_path / "pm2")}
    )
    assert again.status_code == 200 and ProfileStore(isolated_forge_home).names() == ["payments-masking"]

    repo_based = client.post(
        "/api/projects",
        json={
            "mode": "A",
            "project": "Claims export",
            "folder": str(tmp_path / "ce"),
            "repo": str(original_repo),
        },
    )
    assert repo_based.status_code == 200, repo_based.text
    assert client.get("/api/state").json()["workspace"]["mode"] == "A"

    missing_repo = client.post(
        "/api/projects", json={"mode": "A", "project": "x", "folder": str(tmp_path / "x")}
    )
    assert missing_repo.status_code == 400 and "existing project" in missing_repo.json()["detail"]
    no_name = client.post("/api/projects", json={"mode": "B", "project": " ", "folder": str(tmp_path / "y")})
    assert no_name.status_code == 400 and "project name" in no_name.json()["detail"]


def test_attachments_upload_and_resolve_in_a_message(
    client: TestClient, security: ServerSecurity, workspace: Workspace
) -> None:
    # Attach (button / paste / drag-and-drop): stored in .forge/inputs/, referenced as @.forge/inputs/<file>.
    from forge.parity.mentions import expand

    login(client, security)
    client.post("/api/open", json={"workspace": str(workspace.root)})
    text = client.post(
        "/api/upload", params={"name": "../sig nature.py"}, content=b"def mask_pan(pan: str) -> str: ...\n"
    )
    assert text.status_code == 200, text.text
    stored = text.json()
    assert (
        stored["kind"] == "text"
        and stored["path"].startswith(".forge/inputs/")
        and ".." not in stored["path"]
    )
    assert stored["path"].endswith("sig-nature.py")
    image = client.post("/api/upload", params={"name": "scan.png"}, content=b"\x89PNG fake").json()
    pdf = client.post("/api/upload", params={"name": "spec.pdf"}, content=b"%PDF-1.4").json()
    other = client.post("/api/upload", params={"name": "notes.docx"}, content=b"PK..").json()
    assert (image["kind"], pdf["kind"], other["kind"]) == ("image", "pdf", "file")
    assert client.post("/api/upload", params={"name": "empty.txt"}, content=b"").status_code == 400

    mentions = " ".join(f"@{item['path']}" for item in (stored, image, pdf, other))
    message = f"Use these: {mentions} and @.forge/inputs/../state.json"
    expanded = expand(message, workspace)
    assert "def mask_pan(pan: str) -> str" in expanded.text
    assert "look at it with view_image" in expanded.text and len(expanded.images) == 1
    assert "pdf_render" in expanded.text and "can't read this format directly" in expanded.text
    assert "state.json" not in "".join(expanded.notes)  # only files directly in .forge/inputs/


def test_file_search_for_mentions(client: TestClient, security: ServerSecurity, workspace: Workspace) -> None:
    login(client, security)
    client.post("/api/open", json={"workspace": str(workspace.root)})
    found = client.get("/api/files", params={"q": "claims_service"}).json()
    assert found and all("claims_service" in path for path in found)
    assert not [p for p in client.get("/api/files", params={"q": ".env"}).json() if p.endswith(".env")]


def test_setup_secrets_refuses_a_value_with_a_line_break(
    client: TestClient, security: ServerSecurity, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second line in a value would add a second variable to the .env file."""
    monkeypatch.delenv("FORGE_ENV_FILE", raising=False)
    login(client, security)
    evil = "abc\nAZURE_OPENAI_ENDPOINT=https://evil.invalid"  # check_secrets: fake

    refused = client.post(
        "/api/setup/secrets", headers=ORIGIN, json={"values": {"AZURE_OPENAI_API_KEY": evil}}
    )

    assert refused.status_code == 400 and "line break" in refused.json()["detail"]
    assert "evil.invalid" not in env_file_path_text(isolated_forge_home)
    # Whitespace around a pasted value is trimmed, not kept.
    padded = client.post(
        "/api/setup/secrets",
        headers=ORIGIN,
        json={"values": {"AZURE_OPENAI_API_KEY": "  padded-key-123456  "}},
    )
    assert padded.status_code == 200
    assert "AZURE_OPENAI_API_KEY=padded-key-123456\n" in env_file_path_text(isolated_forge_home)


def test_setup_status_lists_the_names_that_can_be_replaced(
    client: TestClient, security: ServerSecurity, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("FORGE_ENV_FILE", raising=False)
    login(client, security)
    status = client.get("/api/setup", headers=ORIGIN).json()
    assert "AZURE_OPENAI_API_KEY" in status["required"] and set(status["missing"]) <= set(status["required"])
