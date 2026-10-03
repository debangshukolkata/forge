"""D-184: the local login (account file, throttling, the gate in front of the API and the WebSocket) and the
project list. No model calls."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from forge.safety.server_security import ServerSecurity
from forge.web.accounts import LOCKOUT_SECONDS, MAX_ATTEMPTS, AccountError, AccountStore
from forge.web.auth_routes import session_cookie_name
from forge.web.manager import WebSessionManager
from forge.web.project_list import describe_projects
from forge.web.server import create_app
from tests.test_web import direct_session

PASSWORD = "correct horse battery"  # check_secrets: fake


def test_account_is_stored_as_a_salted_hash(tmp_path: Path) -> None:
    store = AccountStore(tmp_path)
    assert not store.configured
    token = store.create("asha", PASSWORD)
    text = (tmp_path / "account.json").read_text(encoding="utf-8")
    assert PASSWORD not in text and json.loads(text)["user"] == "asha"
    assert store.signed_in(token) and not store.signed_in("other") and not store.signed_in(None)
    with pytest.raises(AccountError, match="already exists"):
        store.create("someone", PASSWORD)


def test_weak_or_empty_credentials_are_refused(tmp_path: Path) -> None:
    store = AccountStore(tmp_path)
    with pytest.raises(AccountError):
        store.create("  ", PASSWORD)
    with pytest.raises(AccountError, match="at least"):
        store.create("asha", "short")
    assert not store.configured


def test_login_logout_and_the_same_message_for_both_mistakes(tmp_path: Path) -> None:
    store = AccountStore(tmp_path)
    store.create("asha", PASSWORD)
    wrong_user = pytest.raises(AccountError)
    with wrong_user as first:
        store.login("nobody", PASSWORD)
    with pytest.raises(AccountError) as second:
        store.login("asha", "not the password")
    assert str(first.value) == str(second.value)
    token = store.login("asha", PASSWORD)
    assert store.signed_in(token)
    store.logout(token)
    assert not store.signed_in(token)


def test_repeated_wrong_passwords_pause_logins(tmp_path: Path) -> None:
    now = [0.0]
    store = AccountStore(tmp_path, clock=lambda: now[0])
    store.create("asha", PASSWORD)
    for _ in range(MAX_ATTEMPTS):
        with pytest.raises(AccountError):
            store.login("asha", "wrong")
    with pytest.raises(AccountError, match="Too many"):
        store.login("asha", PASSWORD)  # even the right one waits
    now[0] += LOCKOUT_SECONDS + 1
    assert store.signed_in(store.login("asha", PASSWORD))


def test_deleting_the_account_file_resets_it(tmp_path: Path) -> None:
    store = AccountStore(tmp_path)
    store.create("asha", PASSWORD)
    (tmp_path / "account.json").unlink()
    assert not store.configured
    store.create("new-user", PASSWORD)
    assert store.user == "new-user"


@pytest.fixture
def secured(isolated_forge_home: Path) -> Iterator[tuple[TestClient, ServerSecurity]]:
    security = ServerSecurity(port=8798, token="test-token-0123456789")  # check_secrets: fake
    manager = WebSessionManager(isolated_forge_home, direct_session)
    app = create_app(manager, security, accounts=AccountStore(isolated_forge_home))
    with TestClient(app, base_url="http://127.0.0.1:8798") as client:
        yield client, security


def test_the_api_needs_a_signed_in_session(secured: tuple[TestClient, ServerSecurity]) -> None:
    client, security = secured
    origin = {"origin": "http://127.0.0.1:8798"}
    client.get(f"/?t={security.token}", follow_redirects=False)
    assert client.get("/api/state").status_code == 401
    assert client.get("/api/projects").status_code == 401
    assert client.get("/api/auth").json() == {"configured": False, "signed_in": False, "user": None}

    created = client.post("/api/auth/register", json={"user": "asha", "password": PASSWORD}, headers=origin)
    assert created.status_code == 200
    assert client.get("/api/state").status_code == 200
    assert client.get("/api/auth").json()["user"] == "asha"
    assert (
        client.post(
            "/api/auth/register", json={"user": "x", "password": PASSWORD}, headers=origin
        ).status_code
        == 400
    )

    client.post("/api/auth/logout", headers=origin)
    assert client.get("/api/state").status_code == 401
    bad = client.post("/api/auth/login", json={"user": "asha", "password": "nope"}, headers=origin)
    assert bad.status_code == 401
    good = client.post("/api/auth/login", json={"user": "asha", "password": PASSWORD}, headers=origin)
    assert good.status_code == 200 and client.get("/api/projects").json() == []
    cookie = good.headers["set-cookie"]
    assert session_cookie_name(security) in cookie and "HttpOnly" in cookie


def test_websocket_refuses_an_unsigned_session(secured: tuple[TestClient, ServerSecurity]) -> None:
    client, security = secured
    client.get(f"/?t={security.token}", follow_redirects=False)
    ws_url = "ws://127.0.0.1:8798/ws"
    with (
        pytest.raises(WebSocketDisconnect) as refused,
        client.websocket_connect(ws_url, headers={"origin": "http://127.0.0.1:8798"}),
    ):
        pass
    assert refused.value.code == 4401


def test_project_list_shows_last_activity_and_request(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    (root / ".forge" / "transcripts").mkdir(parents=True)
    (root / ".forge" / "workspace.json").write_text("{}", encoding="utf-8")
    lines = [
        {"type": "user_message", "payload": {"text": "first ask"}},
        {"type": "message_done", "payload": {}},
        {"type": "user_message", "payload": {"text": "add  a\nCSV export"}},
        {"type": "message_done", "payload": {}},
    ]
    (root / ".forge" / "transcripts" / "events.jsonl").write_text(
        "\n".join(json.dumps(line) for line in lines), encoding="utf-8"
    )
    [project] = describe_projects(
        [{"path": str(root), "name": "proj", "repo": "standalone (Mode B)", "app_folder": None}]
    )
    assert project["mode"] == "B" and project["last_request"] == "add a CSV export"
    assert project["last_activity"].endswith("+00:00")
    assert (
        describe_projects([{"path": str(tmp_path / "gone"), "name": "x", "repo": "r", "app_folder": None}])
        == []
    )
