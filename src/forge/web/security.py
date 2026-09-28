"""Security of the localhost server (spec §15A.3, A-13): 127.0.0.1 only, a random per-run session token
(not a JWT) carried in an HttpOnly SameSite=Strict cookie, Host/Origin checks against DNS rebinding and
other websites, and a strict Content-Security-Policy."""

from __future__ import annotations

import ipaddress
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlsplit

COOKIE = "forge_token"  # base name; the real cookie is per port (see cookie_name)
LOOPBACK_NAMES = ("127.0.0.1", "localhost")


class BindError(ValueError):
    pass


def check_bind_host(host: str) -> str:
    """Only the loopback interface: the UI drives a coding agent, so it must never be reachable remotely."""
    if host == "localhost":
        return "127.0.0.1"
    try:
        address = ipaddress.ip_address(host)
    except ValueError as error:
        raise BindError(f"Refusing to bind to {host!r}: use 127.0.0.1") from error
    if not address.is_loopback or address.version != 4:
        raise BindError(f"Refusing to bind to {host}: Forge's web UI only listens on 127.0.0.1")
    return host


def check_dev_origin(origin: str) -> str:
    """`forge ui --react --dev`: the Vite dev server's origin — loopback http only, with an explicit port."""
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in LOOPBACK_NAMES
        or not parsed.port
        or parsed.path not in ("", "/")
    ):
        raise BindError(f"Refusing dev origin {origin!r}: use http://127.0.0.1:<port>")
    return f"http://{parsed.hostname}:{parsed.port}"


@dataclass
class ServerSecurity:
    port: int
    token: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    # Only for `forge ui --react --dev`: the Vite dev server that forwards API/WebSocket calls here.
    dev_origin: str | None = None

    @property
    def cookie_name(self) -> str:
        # Browsers share cookies across all ports of 127.0.0.1: the classic UI (8765) and the React UI (8766)
        # would overwrite each other's token with one name.
        return f"{COOKIE}_{self.port}"

    @property
    def allowed_hosts(self) -> set[str]:
        return {f"{name}:{self.port}" for name in LOOPBACK_NAMES}

    @property
    def allowed_origins(self) -> set[str]:
        origins = {f"http://{host}" for host in self.allowed_hosts}
        return origins | ({self.dev_origin} if self.dev_origin else set())

    def token_ok(self, candidate: str | None) -> bool:
        if not candidate:
            return False
        return secrets.compare_digest(candidate.encode(), self.token.encode())

    def check(
        self, headers: Mapping[str, str], cookies: Mapping[str, str], query_token: str | None
    ) -> str | None:
        """None when allowed, else the reason (never echoing the token)."""
        if headers.get("host", "") not in self.allowed_hosts:
            return "unexpected Host header"
        origin = headers.get("origin")
        if origin is not None and origin not in self.allowed_origins:
            return "foreign Origin"
        if not (self.token_ok(cookies.get(self.cookie_name)) or self.token_ok(query_token)):
            return "missing or wrong session token"
        return None

    def content_security_policy(self) -> str:
        sockets = " ".join(f"ws://{host}" for host in sorted(self.allowed_hosts))
        return (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
            f"connect-src 'self' {sockets}; object-src 'none'; base-uri 'none'; form-action 'self'; "
            "frame-ancestors 'none'"
        )

    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/?t={self.token}"
