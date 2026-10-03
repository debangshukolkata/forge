"""The local login (D-184): one account per machine, kept in `<home>/account.json` as a salted scrypt hash.

It keeps other people who share the laptop or the browser out of the projects and keys. It is not protection
against a local administrator, and it never leaves the machine. "Forgot password" means deleting the account
file: the next start offers to create a new account (projects are not touched)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections.abc import Callable
from pathlib import Path

SESSION_COOKIE = "forge_session"
MIN_PASSWORD_LENGTH = 8
MAX_ATTEMPTS = 5  # wrong passwords in a row before a pause
LOCKOUT_SECONDS = 30.0
SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, **SCRYPT)


class AccountError(ValueError):
    """A message safe to show on the login screen."""


class AccountStore:
    def __init__(self, home: Path, clock: Callable[[], float] = time.monotonic) -> None:
        self._file = home / "account.json"
        self._clock = clock
        self._sessions: set[str] = set()
        self._failures = 0
        self._locked_until = 0.0

    def _now(self) -> float:
        return self._clock()

    def _read(self) -> dict[str, str] | None:
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            return data if {"user", "salt", "hash"} <= data.keys() else None
        except (OSError, ValueError, AttributeError):
            return None

    @property
    def configured(self) -> bool:
        return self._read() is not None

    @property
    def user(self) -> str | None:
        account = self._read()
        return account["user"] if account else None

    def create(self, user: str, password: str) -> str:
        """First run only. Returns a session token (the new account is signed in)."""
        if self.configured:
            raise AccountError(
                "An account already exists. To reset it, delete account.json in the Forge folder."
            )
        user = user.strip()
        if not user or len(user) > 64:
            raise AccountError("Enter a user ID (up to 64 characters).")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise AccountError(f"The password needs at least {MIN_PASSWORD_LENGTH} characters.")
        salt = os.urandom(16)
        record = {
            "user": user,
            "salt": base64.b64encode(salt).decode(),
            "hash": base64.b64encode(_hash(password, salt)).decode(),
        }
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(record), encoding="utf-8")
        return self._open_session()

    def login(self, user: str, password: str) -> str:
        account = self._read()
        if account is None:
            raise AccountError("No account yet.")
        if self._now() < self._locked_until:
            wait = int(self._locked_until - self._now()) + 1
            raise AccountError(f"Too many wrong attempts. Try again in {wait} seconds.")
        expected = base64.b64decode(account["hash"])
        actual = _hash(password, base64.b64decode(account["salt"]))
        # Compare both parts without short-circuiting, so the message and timing don't say which was wrong.
        user_ok = hmac.compare_digest(user.strip().encode(), account["user"].encode())
        password_ok = hmac.compare_digest(actual, expected)
        if not (user_ok and password_ok):
            self._failures += 1
            if self._failures >= MAX_ATTEMPTS:
                self._failures = 0
                self._locked_until = self._now() + LOCKOUT_SECONDS
            raise AccountError("The user ID or password is wrong.")
        self._failures = 0
        return self._open_session()

    def _open_session(self) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions.add(token)
        return token

    def signed_in(self, token: str | None) -> bool:
        if not token:
            return False
        return any(secrets.compare_digest(token.encode(), known.encode()) for known in self._sessions)

    def logout(self, token: str | None) -> None:
        if token:
            self._sessions.discard(token)
