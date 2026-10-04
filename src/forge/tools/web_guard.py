"""Which addresses the web tools may reach (D-209).

web_fetch and the headless browser run on the user's machine, on the company network, so a URL the model picks
(or a page tells it to open) could point at localhost, an intranet wiki or git server, or a cloud metadata
address. Those are refused unless the user listed the host in `web.allow_hosts`; domain deny/allow lists
come from the same config. Every redirect hop and every browser sub-request is checked again."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any
from urllib.parse import urlparse

INTERNAL_NAMES = ("localhost", "metadata", "metadata.google.internal")
INTERNAL_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa", ".lan")
LOCAL_SCHEMES = ("data", "blob", "about")  # inside a page, never a network address


@dataclass(frozen=True)
class WebPolicy:
    allow_hosts: tuple[str, ...] = ()  # internal hosts the user allowed: exact name, domain or wildcard
    deny_domains: tuple[str, ...] = ()
    allow_domains: tuple[str, ...] = ()  # when not empty, only these domains (and their subdomains)

    @classmethod
    def from_config(cls, web: Any) -> WebPolicy:
        return cls(tuple(web.allow_hosts), tuple(web.deny_domains), tuple(web.allow_domains))


def host_matches(host: str, patterns: tuple[str, ...]) -> bool:
    host = host.lower().rstrip(".")
    return any(
        host == p.lower() or host.endswith("." + p.lower().lstrip("*.")) or fnmatchcase(host, p.lower())
        for p in patterns
    )


def _is_internal_address(text: str) -> bool:
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return not address.is_global  # private, loopback, link-local, shared (100.64/10), reserved, multicast


def check_url(url: str, policy: WebPolicy) -> str | None:
    """None when the URL may be fetched, else why not. Looks at the text only; see check_resolving."""
    parsed = urlparse(url)
    if parsed.scheme in LOCAL_SCHEMES:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return "only http(s) addresses can be fetched"
    if parsed.username or parsed.password:
        return "an address with a user name or password in it is not fetched"
    host = parsed.hostname.lower().rstrip(".")
    if policy.deny_domains and host_matches(host, policy.deny_domains):
        return f"{host} is in web.deny_domains"
    if policy.allow_domains and not host_matches(host, policy.allow_domains):
        return f"{host} is not in web.allow_domains"
    internal = host in INTERNAL_NAMES or host.endswith(INTERNAL_SUFFIXES) or _is_internal_address(host)
    if internal and not host_matches(host, policy.allow_hosts):
        return _INTERNAL.format(host=host)
    return None


_INTERNAL = (
    "{host} is a local or internal address (this computer, an intranet or a cloud metadata service). "
    "The user can allow it with web.allow_hosts; otherwise ask them to paste the content"
)


async def check_resolving(url: str, policy: WebPolicy) -> str | None:
    """check_url, plus: a public-looking name that resolves to an internal address is refused too."""
    reason = check_url(url, policy)
    parsed = urlparse(url)
    if reason is not None or parsed.scheme in LOCAL_SCHEMES or not parsed.hostname:
        return reason
    host = parsed.hostname.lower().rstrip(".")
    if _is_literal_address(host) or host_matches(host, policy.allow_hosts):
        return None
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError:
        return None  # cannot be resolved: the request itself will fail with a clearer message
    if any(_is_internal_address(str(info[4][0])) for info in infos):
        return _INTERNAL.format(host=f"{host} (it resolves to an internal address)")
    return None


def _is_literal_address(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True
