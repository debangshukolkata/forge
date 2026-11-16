"""D-627: the connection indicators of the top bar: the state of each sign-in and each tunnel, worked out when asked."""

# ruff: noqa: F811  (fixtures are imported from tests.test_web)

from __future__ import annotations

import json
import socket
import time
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from forge.db import tunnel
from forge.safety.server_security import ServerSecurity
from forge.toolkit import field_log
from forge.toolkit.app_logins import TokenStore
from forge.tools.app_login import Ensured
from tests.test_app_logins import GOOD, jwt, write_logins
from tests.test_web import client, login, security  # noqa: F401  (fixtures)


def _items(client: TestClient, query: str = "") -> dict[str, dict[str, object]]:
    response = client.get(f"/api/connections{query}")
    assert response.status_code == 200
    return {f"{item['kind']}:{item['name']}": item for item in response.json()["items"]}


def test_nothing_set_up_gives_no_indicator(client: TestClient, security: ServerSecurity) -> None:
    login(client, security)
    assert _items(client) == {}


def test_each_sign_in_and_tunnel_has_a_state_and_no_token_is_shown(
    client: TestClient, security: ServerSecurity, isolated_forge_home: Path
) -> None:
    login(client, security)
    write_logins(isolated_forge_home, GOOD)
    token = jwt(exp=time.time() + 42 * 60 + 30)
    TokenStore(isolated_forge_home).put("DEV_TOKEN", token)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        (isolated_forge_home / "tunnels.yaml").write_text(
            yaml.safe_dump(
                {
                    "tunnels": {
                        "dev": {"command": ["gcloud", "x"], "port": listener.getsockname()[1]},
                        "sit": {"command": ["gcloud", "y"], "port": 1},
                    }
                }
            ),
            encoding="utf-8",
        )
        items = _items(client)
        text = json.dumps(items)
    assert items["login:dev"]["state"] == "ok" and "signed in, 42 min left" in str(
        items["login:dev"]["detail"]
    )
    assert items["login:sit"]["state"] == "none" and "at the first call" in str(items["login:sit"]["detail"])
    assert items["tunnel:dev"]["state"] == "ok" and "open on port" in str(items["tunnel:dev"]["detail"])
    assert items["tunnel:sit"]["state"] == "none" and "opens when" in str(items["tunnel:sit"]["detail"])
    assert token not in text

    # a sign-in that failed, and a tunnel that could not be opened, are red with the reason
    field_log.write(
        "sign_in", isolated_forge_home, env="sit", ok=False, detail="the page asked for a Google login"
    )
    tunnel.last_problem["sit"] = "The Google login looks expired: run gcloud auth login."
    try:
        items = _items(client)
    finally:
        tunnel.last_problem.clear()
    assert items["login:sit"]["state"] == "failed" and "Google login" in str(items["login:sit"]["detail"])
    assert items["tunnel:sit"]["state"] == "failed" and "gcloud auth login" in str(
        items["tunnel:sit"]["detail"]
    )


def test_a_file_that_cannot_be_used_is_one_red_indicator(
    client: TestClient, security: ServerSecurity, isolated_forge_home: Path
) -> None:
    login(client, security)
    (isolated_forge_home / "app_logins.yaml").write_text("environments: [1, 2]\n", encoding="utf-8")
    items = _items(client)
    assert list(items) == ["login:app_logins.yaml"] and items["login:app_logins.yaml"]["state"] == "failed"


def test_the_buttons_sign_in_and_open_the_tunnel_only_for_what_the_user_set_up(
    client: TestClient, security: ServerSecurity, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    login(client, security)
    write_logins(isolated_forge_home, GOOD)
    (isolated_forge_home / "tunnels.yaml").write_text(
        yaml.safe_dump({"tunnels": {"dev": {"command": ["no-such-program-xyz"], "port": 1}}}),
        encoding="utf-8",
    )
    asked: list[str] = []

    async def fake_ensure(found, home=None, ask=None, force=False):  # type: ignore[no-untyped-def]
        asked.append(found.name)
        TokenStore(home).put(found.token_name, jwt(exp=time.time() + 600))
        return Ensured("a-token")

    monkeypatch.setattr("forge.web.connection_routes.ensure_token", fake_ensure)
    signed = client.post("/api/connections/sign-in", json={"name": "sit"}).json()
    assert signed["ok"] and asked == ["sit"] and "a-token" not in json.dumps(signed)
    assert next(i for i in signed["items"] if i["name"] == "sit" and i["kind"] == "login")["state"] == "ok"
    assert client.post("/api/connections/sign-in", json={"name": "prod"}).status_code == 404

    try:
        opened = client.post("/api/connections/tunnel", json={"name": "dev"}).json()
        assert not opened["ok"] and "not on the PATH" in opened["message"]
        assert next(i for i in opened["items"] if i["kind"] == "tunnel")["state"] == "failed"
    finally:
        tunnel.last_problem.clear()
    assert client.post("/api/connections/tunnel", json={"name": "other"}).status_code == 404


def test_the_connections_need_the_login_like_every_other_address(client: TestClient) -> None:
    assert client.get("/api/connections").status_code in (401, 403)
    assert client.post("/api/connections/sign-in", json={"name": "dev"}).status_code in (401, 403)
