"""Database connections for Forge's own work (spec §9.5.2 "good citizen"): timeouts on every session,
read-only sessions for real schemas, search_path pinned to the scratch schema for scratch work."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import psycopg

from forge.config import Secrets

CONNECT_TIMEOUT_S = 5
IDLE_IN_TRANSACTION_S = 60
_SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


@dataclass
class DbTarget:
    name: str  # "local" or "dev"
    url_env: str
    sslmode: str = "prefer"
    statement_timeout_s: int = 30
    lock_timeout_s: int = 5

    def url(self, secrets: Secrets) -> str | None:
        return secrets.get(self.url_env)


def safe_schema_name(name: str) -> str:
    """Schema names are interpolated into SET/CREATE statements, so only plain identifiers are allowed."""
    if not _SCHEMA_NAME.match(name):
        raise ValueError(f"Invalid schema name {name!r}: use lower-case letters, digits and underscores.")
    return name


def connect(
    target: DbTarget, secrets: Secrets, *, read_only: bool = False, search_path: str | None = None
) -> psycopg.Connection[Any]:
    url = target.url(secrets)
    if not url:
        raise psycopg.OperationalError(f"{target.url_env} is not set in Forge's .env")
    options = [
        f"-c statement_timeout={target.statement_timeout_s * 1000}",
        f"-c lock_timeout={target.lock_timeout_s * 1000}",
        f"-c idle_in_transaction_session_timeout={IDLE_IN_TRANSACTION_S * 1000}",
        "-c application_name=forge",
    ]
    if read_only:
        options.append("-c default_transaction_read_only=on")
    if search_path:
        options.append(f"-c search_path={safe_schema_name(search_path)}")
    return psycopg.connect(
        url,
        connect_timeout=CONNECT_TIMEOUT_S,
        sslmode=target.sslmode,
        options=" ".join(options),
        autocommit=True,
        keepalives=1,
        keepalives_idle=30,
    )


def explain_connection_error(error: Exception) -> str:
    """A one-line, human reason for an L1 (no connection) result."""
    text = str(error).lower()
    if "not set in forge" in text:
        return str(error)
    if (
        "could not translate host name" in text
        or "name or service not known" in text
        or "no such host" in text
    ):
        return "the host name can't be resolved. Are you on the VPN?"
    if "timeout" in text or "timed out" in text:
        return "the server didn't answer in time. Are you on the VPN, and is the port open?"
    if "connection refused" in text:
        return "nothing is listening on that host and port. Is the server running?"
    if "password authentication failed" in text or "authentication" in text:
        return "the user name or password was rejected."
    if "ssl" in text:
        return "SSL settings don't match the server's (check sslmode in config)."
    if "does not exist" in text and "database" in text:
        return "the database named in the URL doesn't exist."
    return str(error).strip().splitlines()[0][:200]
