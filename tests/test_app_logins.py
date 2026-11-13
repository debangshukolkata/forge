"""D-603: app logins, the private token store, and the host rules of http_request (no browser, no model)."""

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

from forge.errors import ConfigError
from forge.toolkit.app_logins import (
    TokenStore,
    jwt_expiry,
    load_logins,
    login_for_host,
    login_for_token,
)
from forge.toolkit.base import ToolContext
from forge.tools.http_request import HttpRequest
from forge.workspace.create import create_workspace

FAKE_JWT_SIGNATURE = "s3cretpart" * 3  # check_secrets: fake


def jwt(exp: float | None = None) -> str:
    def part(data: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")

    payload: dict[str, object] = {"sub": "u1"}
    if exp is not None:
        payload["exp"] = exp
    return f"{part({'alg': 'HS256', 'typ': 'JWT'})}.{part(payload)}.{FAKE_JWT_SIGNATURE}"


GOOD = {
    "environments": {
        "dev": {
            "login_url": "https://dev.example.com/app/login/",
            "token_name": "DEV_TOKEN",
            "token": {"cookie": "access_token_cookie"},
            "steps": [{"click": "Sign in"}, {"wait_url": "uuid_key"}, {"click": "Proceed"}, {"pause": 1}],
        },
        "sit": {
            "login_url": "http://127.0.0.2:9/x/login/",
            "token_name": "SIT_TOKEN",
            "token": {"header": "Authorization"},
        },
    }
}


def write_logins(home: Path, data: object) -> None:
    (home / "app_logins.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")


def test_the_environments_are_read_from_the_users_file(isolated_forge_home: Path) -> None:
    assert load_logins(isolated_forge_home) == {}  # no file: no remote host
    write_logins(isolated_forge_home, GOOD)
    logins = load_logins(isolated_forge_home)
    dev = logins["dev"]
    assert (
        dev.host == "dev.example.com" and dev.token_cookie == "access_token_cookie" and dev.token_header == ""
    )
    assert [s.action for s in dev.steps] == ["click", "wait_url", "click", "pause"] and dev.steps[
        3
    ].seconds == 1
    assert logins["sit"].token_header == "authorization" and logins["sit"].steps == ()
    assert login_for_host("DEV.example.com", isolated_forge_home) == dev
    assert login_for_token("SIT_TOKEN", isolated_forge_home) == logins["sit"]
    assert login_for_host("other.example.com", isolated_forge_home) is None


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"login_url": "ftp://x"}, "http\\(s\\) address"),
        ({"token_name": "not a name!"}, "token_name"),
        ({"token": {"cookie": "a", "header": "b"}}, "either a `cookie` or a `header`"),
        ({"token": {}}, "either a `cookie` or a `header`"),
        ({"steps": [{"tap": "x"}]}, "unknown step"),
        ({"steps": [{"click": ""}]}, "needs a text"),
        ({"steps": ["click"]}, "each step"),
    ],
)
def test_a_wrong_description_says_what_is_wrong(
    isolated_forge_home: Path, change: dict, message: str
) -> None:  # type: ignore[type-arg]
    broken = json.loads(json.dumps(GOOD))
    broken["environments"]["dev"].update(change)
    write_logins(isolated_forge_home, broken)
    with pytest.raises(ConfigError, match=message):
        load_logins(isolated_forge_home)


def test_a_file_that_is_not_yaml_says_so(isolated_forge_home: Path) -> None:
    (isolated_forge_home / "app_logins.yaml").write_text("environments: [", encoding="utf-8")
    with pytest.raises(ConfigError, match="not valid YAML"):
        load_logins(isolated_forge_home)


def test_the_token_store_keeps_tokens_until_they_end_and_masks_them(isolated_forge_home: Path) -> None:
    from forge.safety.redact import default_redactor

    store = TokenStore(isolated_forge_home)
    assert store.get("DEV_TOKEN") is None
    token = jwt(exp=time.time() + 3600)
    seconds = store.put("DEV_TOKEN", token)
    assert 3500 < seconds <= 3600 and store.get("DEV_TOKEN") == token
    assert token not in default_redactor.redact(f"the header was Bearer {token}")  # registered for masking

    store.put("OLD", jwt(exp=time.time() + 30))  # ends within the renewal margin: treated as ended
    assert store.get("OLD") is None
    store.put("NOEXP", jwt())  # a token without an expiry is kept for a default time
    assert store.get("NOEXP") is not None
    store.forget("DEV_TOKEN")
    assert store.get("DEV_TOKEN") is None and store.get("NOEXP") is not None
    assert jwt_expiry("not a jwt") is None and jwt_expiry("a.b.c") is None


class Remote(BaseHTTPRequestHandler):
    """Answers 200 only to the current token; records what it was sent."""

    valid: ClassVar[str] = "token-one"
    seen: ClassVar[list[str]] = []

    def do_GET(self) -> None:
        sent = self.headers.get("Authorization", "")
        Remote.seen.append(sent)
        status = 200 if sent == f"Bearer {Remote.valid}" else 401
        body = json.dumps({"hello": "world"}).encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def remote(isolated_forge_home: Path, original_repo: Path, tmp_path: Path):  # type: ignore[no-untyped-def]
    """A 'remote' host on the loopback alias 127.0.0.2 (not one of the local names), listed by the user."""
    server = ThreadingHTTPServer(("127.0.0.2", 0), Remote)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    Remote.seen = []
    Remote.valid = "token-one"
    write_logins(
        isolated_forge_home,
        {
            "environments": {
                "sit": {
                    "login_url": "http://127.0.0.2:9/x/login/",
                    "token_name": "SIT_TOKEN",
                    "token": {"cookie": "t"},
                }
            }
        },
    )
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    yield f"http://127.0.0.2:{server.server_port}/api", context, isolated_forge_home
    server.shutdown()


async def call(context: ToolContext, url: str, **fields: object):  # type: ignore[no-untyped-def]
    return await HttpRequest().run(HttpRequest.Args(method="GET", url=url, **fields), context)  # type: ignore[arg-type]


def approve(context: ToolContext) -> None:
    (context.workspace.forge_dir / "remote_hosts.json").write_text(
        json.dumps(["127.0.0.2"]), encoding="utf-8"
    )


async def test_a_host_the_user_did_not_list_is_refused(remote) -> None:  # type: ignore[no-untyped-def]
    _, context, _ = remote
    result = await call(context, "http://127.0.0.3:80/api")
    assert not result.ok and "neither" in result.content
    assert not (await call(context, "ftp://127.0.0.2/x")).ok


async def test_a_listed_host_needs_the_users_card_once_and_the_answer_is_kept(remote) -> None:  # type: ignore[no-untyped-def]
    url, context, home = remote
    TokenStore(home).put("SIT_TOKEN", "token-one")
    asked: list[str] = []

    async def deny(question: str, detail: str, options: list[object], default: str | None) -> str:
        asked.append(question)
        return "The user chose: Do not allow"

    context.ask_user = deny  # type: ignore[assignment]
    refused = await call(context, url, token_env="SIT_TOKEN")
    assert not refused.ok and "did not allow" in refused.content and Remote.seen == []

    async def allow(question: str, detail: str, options: list[object], default: str | None) -> str:
        asked.append(question)
        return "The user chose: Allow"

    context.ask_user = allow  # type: ignore[assignment]
    sent = await call(context, url, token_env="SIT_TOKEN")
    assert sent.ok and "HTTP 200" in sent.content and Remote.seen == ["Bearer token-one"]
    assert "token-one" not in sent.content

    context.ask_user = None
    again = await call(context, url, token_env="SIT_TOKEN")  # approved for this project: no card needed
    assert again.ok and len(asked) == 2


async def test_a_401_signs_in_again_once_and_repeats_the_call(remote, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    url, context, home = remote
    approve(context)
    TokenStore(home).put("SIT_TOKEN", "token-stale")
    renewals: list[str] = []

    async def fake_renew(login, home=None):  # type: ignore[no-untyped-def]
        from forge.tools.app_login import SignIn

        renewals.append(login.name)
        Remote.valid = "token-fresh"
        TokenStore(home).put(login.token_name, "token-fresh")
        return SignIn(True, token="token-fresh")

    monkeypatch.setattr("forge.tools.http_request.renew", fake_renew)
    result = await call(context, url, token_env="SIT_TOKEN")

    assert result.ok and "HTTP 200" in result.content and "signed in again" in result.content
    assert renewals == ["sit"] and Remote.seen == ["Bearer token-stale", "Bearer token-fresh"]
    assert "token-fresh" not in result.content and "token-stale" not in result.content


async def test_a_token_for_one_host_is_not_sent_to_another(remote) -> None:  # type: ignore[no-untyped-def]
    _, context, home = remote
    TokenStore(home).put("SIT_TOKEN", "token-one")
    result = await call(context, "http://127.0.0.3:80/x", token_env="SIT_TOKEN")
    assert not result.ok  # refused before anything is sent: not a host the user listed


async def test_a_token_that_ended_and_cannot_be_renewed_says_so(remote, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    url, context, _ = remote
    approve(context)

    async def needs_person(login, home=None):  # type: ignore[no-untyped-def]
        from forge.tools.app_login import SignIn

        return SignIn(False, message="Step 1 did not complete", needs_user=True)

    monkeypatch.setattr("forge.tools.http_request.renew", needs_person)
    result = await call(context, url, token_env="SIT_TOKEN")
    assert not result.ok and "SIT_TOKEN is not available" in result.content
