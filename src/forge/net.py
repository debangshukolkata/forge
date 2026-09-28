"""Network setup for enterprise laptops (DECISIONS D-110).

Company networks often inspect HTTPS with their own root certificate, which Windows trusts but Python's
bundled certificate list does not: every Azure call then fails with a bare "Connection error". truststore
makes Python verify certificates against the operating system's store, so whatever Windows trusts, Forge
trusts — no certificate files to export. Set FORGE_SYSTEM_CERTS=0 to keep Python's own list.
"""

from __future__ import annotations

import os

_state = {"done": False, "active": False}


def use_system_certificates() -> bool:
    """Idempotent; returns whether the OS certificate store is in use. Never raises."""
    if _state["done"]:
        return _state["active"]
    _state["done"] = True
    if os.environ.get("FORGE_SYSTEM_CERTS", "1").strip().lower() in {"0", "false", "no"}:
        return False
    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception:  # optional: without it Python's own certificate list applies, as before
        return False
    _state["active"] = True
    return True


def connection_hint(detail: str) -> str:
    """A one-line next step for the usual causes of 'could not reach the endpoint' on a company laptop."""
    lowered = detail.lower()
    if "certificate" in lowered or "ssl" in lowered:
        return (
            "the company's HTTPS inspection certificate isn't trusted: keep FORGE_SYSTEM_CERTS unset (Forge "
            "then uses the Windows certificate store) and make sure the 'truststore' package is installed"
        )
    if "getaddrinfo" in lowered or "name or service not known" in lowered or "nodename" in lowered:
        return "the endpoint's host name can't be resolved: check AZURE_OPENAI_ENDPOINT, VPN or DNS"
    if "407" in lowered or "proxy" in lowered:
        return "the proxy refused the request: check HTTPS_PROXY (and proxy credentials)"
    if "timed out" in lowered or "timeout" in lowered:
        return "no answer in time: a proxy is probably required — set HTTPS_PROXY for your user"
    return "check AZURE_OPENAI_ENDPOINT, the network/VPN, and whether a proxy is required (HTTPS_PROXY)"


def root_cause(error: BaseException) -> str:
    """The innermost exception in the cause chain as 'Type: message' (openai only says 'Connection error')."""
    seen = set()
    current: BaseException | None = error
    last = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        last = current
        current = current.__cause__ or current.__context__
    return f"{type(last).__name__}: {last}"
