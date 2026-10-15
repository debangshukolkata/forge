"""Network setup for enterprise laptops (DECISIONS D-110).

Company networks often inspect HTTPS with their own root certificate, which Windows trusts but Python's
bundled certificate list does not: every Azure call then fails with a bare "Connection error". truststore
makes Python verify certificates against the operating system's store, so whatever Windows trusts, DebCraft
trusts — no certificate files to export. Set FORGE_SYSTEM_CERTS=0 to keep Python's own list.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

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


def connection_hint(detail: str, target: str = "AZURE_OPENAI_ENDPOINT") -> str:
    """A one-line next step for the usual causes of 'could not reach the endpoint' on a company laptop."""
    lowered = detail.lower()
    if "certificate" in lowered or "ssl" in lowered:
        return (
            "the company's HTTPS inspection certificate isn't trusted: keep FORGE_SYSTEM_CERTS unset (DebCraft "
            "then uses the Windows certificate store) and make sure the 'truststore' package is installed"
        )
    if "getaddrinfo" in lowered or "name or service not known" in lowered or "nodename" in lowered:
        return f"the host name can't be resolved: check {target}, VPN or DNS"
    if "407" in lowered or "proxy" in lowered:
        return "the proxy refused the request: check HTTPS_PROXY (and proxy credentials)"
    if "timed out" in lowered or "timeout" in lowered:
        return "no answer in time: a proxy is probably required — set HTTPS_PROXY for your user"
    return f"check {target}, the network/VPN, and whether a proxy is required (HTTPS_PROXY)"


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


def system_certificates_wanted() -> bool:
    return os.environ.get("FORGE_SYSTEM_CERTS", "1").strip().lower() not in {"0", "false", "no"}


def node_supports_system_ca(version: str) -> bool:
    """Node reads the operating system's certificate store with NODE_USE_SYSTEM_CA=1 from 22.15, 23.8 and 24 on (D-363)."""
    match = re.match(r"v?(\d+)\.(\d+)", version.strip())
    if not match:
        return False
    major, minor = int(match.group(1)), int(match.group(2))
    return major >= 24 or (major == 23 and minor >= 8) or (major == 22 and minor >= 15)


def installed_node_version() -> str | None:
    node = shutil.which("node")
    if not node:
        return None
    try:
        done = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout.strip() or None


# What Node, npm and curl-like tools print when a company's HTTPS inspection certificate is not trusted (D-402).
CERTIFICATE_ERROR = re.compile(
    r"unable to get local issuer certificate|self[- ]signed certificate|UNABLE_TO_VERIFY_LEAF_SIGNATURE|"
    r"unable to verify the first certificate|SELF_SIGNED_CERT_IN_CHAIN|CERT_UNTRUSTED|SSL certificate problem",
    re.IGNORECASE,
)


def looks_like_certificate_error(output: str) -> bool:
    return bool(CERTIFICATE_ERROR.search(output))


def windows_certificate_bundle(target: Path) -> Path | None:
    """Writes the certificates Windows trusts (the Root and Intermediate stores of the current user and the machine) as one PEM file and returns its path.

    Node ignores the Windows store before version 22.15, and even a new Node can be run with FORGE_SYSTEM_CERTS=0; `NODE_EXTRA_CA_CERTS` pointing at this file gives
    every Node tool the company's inspection root without anyone exporting a certificate by hand. Needs no administrator rights. None off Windows or when nothing could be read."""
    import ssl
    import sys

    if sys.platform != "win32":
        return None
    pems: list[str] = []
    seen: set[bytes] = set()
    for store in ("ROOT", "CA"):
        try:
            entries = ssl.enum_certificates(store)
        except (OSError, AttributeError):
            continue
        for der, encoding, _trust in entries:
            if encoding != "x509_asn" or der in seen:
                continue
            seen.add(der)
            pems.append(ssl.DER_cert_to_PEM_cert(der))
    if not pems:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(pems), encoding="ascii", newline=chr(10))
    return target
