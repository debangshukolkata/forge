"""App logins and the token store (D-603).

The user describes once, in `<DebCraft Home>/app_logins.yaml`, how to sign in to each environment of a web application
(the dev and SIT sites): the login address, the buttons to click by their text, the address to wait for, and where the
token appears (a cookie or a request header) and the NAME it is kept under. The model cannot change this file.

    environments:
      dev:
        login_url: https://dev.example.com/app/login/
        token_name: DEV_TOKEN
        token: {cookie: access_token_cookie}      # or {header: authorization}
        steps:
          - click: "Sign in"
          - wait_url: "uuid_key"
          - click: "Proceed"
          - wait_url: "landing-home"
        check_url: https://dev.example.com/app/api/me   # optional: a cheap call that tells whether the token is valid
        warn_without_token: true                         # optional: warn at session start without a valid token

The tokens a login produces are kept in a private store: memory and the file `tokens.json` in DebCraft Home. They are
never written into an environment file (values there reach every command the model runs), never shown, registered with
the redactor, used by name by `http_request`, and only sent to the hosts of the environments listed here."""

from __future__ import annotations

import base64
import contextlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from forge.config import forge_home
from forge.errors import ConfigError
from forge.safety.redact import default_redactor

LOGINS_FILE = "app_logins.yaml"
TOKENS_FILE = "tokens.json"
DEFAULT_LIFETIME_S = 50 * 60  # a token without an `exp` claim is renewed after this long
RENEW_BEFORE_S = 120  # a token that ends within this is treated as expired
STEP_ACTIONS = ("click", "wait_url", "pause")


@dataclass(frozen=True)
class Step:
    action: str  # click | wait_url | pause
    value: str = ""
    seconds: float = 0.0


@dataclass(frozen=True)
class EnvLogin:
    name: str
    login_url: str
    token_name: str
    token_cookie: str
    token_header: str
    steps: tuple[Step, ...]
    check_url: str = (
        ""  # a cheap authenticated address: 2xx means the token is valid, 401 or 403 that it is not
    )
    warn_without_token: bool = False  # at the start of a session, warn the user when there is no valid token

    @property
    def host(self) -> str:
        return (urlparse(self.login_url).hostname or "").lower()


def _step(raw: Any, where: str) -> Step:
    if not isinstance(raw, dict) or len(raw) != 1:
        raise ConfigError(
            f'{where}: each step is one of {", ".join(STEP_ACTIONS)}, written as `- click: "Sign in"`.'
        )
    (action, value), *_ = raw.items()
    if action not in STEP_ACTIONS:
        raise ConfigError(f"{where}: unknown step `{action}` (use {', '.join(STEP_ACTIONS)}).")
    if action == "pause":
        return Step("pause", seconds=float(value))
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{where}: `{action}` needs a text.")
    return Step(action, value=value)


def _parse(name: str, raw: Any) -> EnvLogin:
    where = f"{LOGINS_FILE}, environment {name!r}"
    if not isinstance(raw, dict):
        raise ConfigError(f"{where}: expected settings (login_url, token_name, token, steps).")
    login_url = str(raw.get("login_url", "")).strip()
    parsed = urlparse(login_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ConfigError(f"{where}: `login_url` must be an http(s) address.")
    token_name = str(raw.get("token_name", "")).strip()
    if not token_name or not token_name.replace("_", "").isalnum():
        raise ConfigError(f"{where}: `token_name` is a plain name such as DEV_TOKEN.")
    token = raw.get("token") or {}
    cookie, header = str(token.get("cookie", "")).strip(), str(token.get("header", "")).strip().lower()
    if bool(cookie) == bool(header):
        raise ConfigError(f"{where}: `token` names either a `cookie` or a `header`, one of them.")
    steps = tuple(
        _step(item, f"{where}, step {number}") for number, item in enumerate(raw.get("steps") or [], 1)
    )
    check_url = str(raw.get("check_url", "")).strip()
    if check_url:
        checked = urlparse(check_url)
        if (
            checked.scheme not in ("http", "https")
            or (checked.hostname or "").lower() != parsed.hostname.lower()
        ):
            raise ConfigError(
                f"{where}: `check_url` must be an http(s) address on the same host as `login_url`."
            )
    warn = bool(raw.get("warn_without_token", False))
    return EnvLogin(name, login_url, token_name, cookie, header, steps, check_url, warn)


def load_logins(home: Path | None = None) -> dict[str, EnvLogin]:
    """The environments the user described; {} when there is no file. A file that cannot be read says why."""
    path = (home or forge_home()) / LOGINS_FILE
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as error:
        raise ConfigError(f"{LOGINS_FILE} is not valid YAML: {error}") from error
    environments = data.get("environments") if isinstance(data, dict) else None
    if not isinstance(environments, dict):
        raise ConfigError(f"{LOGINS_FILE} needs an `environments:` section.")
    return {str(name): _parse(str(name), raw) for name, raw in environments.items()}


def login_for_host(host: str, home: Path | None = None) -> EnvLogin | None:
    """The environment whose login address is on this host: the only remote hosts `http_request` may call."""
    host = host.lower()
    return next((login for login in load_logins(home).values() if login.host == host), None)


def login_for_token(name: str, home: Path | None = None) -> EnvLogin | None:
    return next((login for login in load_logins(home).values() if login.token_name == name), None)


def jwt_expiry(token: str) -> float | None:
    """The `exp` claim of a JWT (not a secret), or None when the token is no JWT or has no expiry."""
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4)))
    except (ValueError, TypeError):
        return None
    exp = payload.get("exp") if isinstance(payload, dict) else None
    return float(exp) if isinstance(exp, int | float) else None


class TokenStore:
    """name -> token with its expiry, in `tokens.json` of DebCraft Home (private to the user's account)."""

    def __init__(self, home: Path | None = None) -> None:
        self.path = (home or forge_home()) / TOKENS_FILE

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def get(self, name: str) -> str | None:
        """The token while it is valid for at least a little longer; registers it with the redactor."""
        entry = self._load().get(name)
        if not isinstance(entry, dict) or not isinstance(entry.get("token"), str):
            return None
        if float(entry.get("expires_at", 0)) - time.time() < RENEW_BEFORE_S:
            return None
        token: str = entry["token"]
        default_redactor.register(token, name)
        return token

    def remaining(self, name: str) -> int | None:
        entry = self._load().get(name)
        if not isinstance(entry, dict):
            return None
        return max(0, int(float(entry.get("expires_at", 0)) - time.time()))

    def lifetime(self, name: str) -> tuple[int, bool] | None:
        """How long the stored token lasted from the moment DebCraft got it to its end, in seconds, and whether
        that end is the token's own `exp` claim. Numbers only: the token itself is not returned."""
        entry = self._load().get(name)
        if not isinstance(entry, dict) or "obtained" not in entry:
            return None
        span = int(float(entry.get("expires_at", 0)) - float(entry["obtained"]))
        return max(0, span), bool(entry.get("from_claim", False))

    def put(self, name: str, token: str) -> int:
        """Keeps a token; returns the seconds it is valid for. The file is replaced atomically and made private."""
        default_redactor.register(token, name)
        claimed = jwt_expiry(token)
        expires_at = claimed or time.time() + DEFAULT_LIFETIME_S
        data = self._load()
        # `from_claim`: the end is the token's own `exp`, not DebCraft's guess (the facts report says which).
        data[name] = {
            "token": token,
            "expires_at": expires_at,
            "obtained": int(time.time()),
            "from_claim": claimed is not None,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        scratch = self.path.with_suffix(".tmp")
        scratch.write_text(json.dumps(data), encoding="utf-8")
        with contextlib.suppress(
            OSError
        ):  # POSIX: owner only; on Windows the file is in the user's own profile
            os.chmod(scratch, 0o600)
        scratch.replace(self.path)
        return max(0, int(expires_at - time.time()))

    def forget(self, name: str) -> None:
        data = self._load()
        if data.pop(name, None) is not None:
            self.path.write_text(json.dumps(data), encoding="utf-8")
