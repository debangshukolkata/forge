"""Helpers of a small file-sharing service. The web layer calls them with values taken from the request.

Each function's docstring says what it is for and how it may fail."""

from __future__ import annotations

import hmac
import io
import ipaddress
import re
import secrets
import sqlite3
import string
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit

MAX_TOTAL_BYTES = 10 * 1024 * 1024
MAX_ENTRIES = 1000


class UploadError(ValueError):
    """The upload cannot be accepted; the message says why."""


class FetchRefused(ValueError):
    """The address may not be fetched."""


def _safe_member(name: str) -> PurePosixPath:
    """The entry's relative path, or UploadError when it could land outside the destination on any platform."""
    if not name or "\x00" in name:
        raise UploadError(f"bad entry name {name!r}")
    windows = PureWindowsPath(name)
    posix = PurePosixPath(name.replace("\\", "/"))
    if windows.drive or windows.root or posix.is_absolute() or ".." in posix.parts:
        raise UploadError(f"entry {name!r} would land outside the destination")
    return posix


def extract_upload(data: bytes, destination: str | Path) -> list[str]:
    """Unpack a zip upload into `destination` and return the relative names of the files written, in archive order.

    Folders inside the archive are kept. An archive with more than MAX_ENTRIES entries, or whose files would take more than
    MAX_TOTAL_BYTES once unpacked, is refused with UploadError, as is a file that is not a zip archive. Nothing may be written
    outside `destination`: an entry that would land outside it is refused with UploadError and nothing is written at all."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise UploadError("not a zip archive") from error
    entries = archive.infolist()
    if len(entries) > MAX_ENTRIES:
        raise UploadError(f"more than {MAX_ENTRIES} entries")
    root = Path(destination).resolve()
    plan = []
    declared = 0
    for info in entries:
        member = _safe_member(info.filename)
        if info.is_dir():
            continue
        target = (root / member).resolve()
        if root not in target.parents:
            raise UploadError(f"entry {info.filename!r} would land outside the destination")
        declared += info.file_size
        if declared > MAX_TOTAL_BYTES:
            raise UploadError("the archive is too large once unpacked")
        plan.append((info, target))
    written = []
    total = 0
    for info, target in plan:
        # The sizes in the archive can lie, so the real bytes are counted while reading.
        with archive.open(info) as source:
            content = source.read(MAX_TOTAL_BYTES - total + 1)
        total += len(content)
        if total > MAX_TOTAL_BYTES:
            raise UploadError("the archive is too large once unpacked")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        written.append(info.filename)
    return written


def _is_public(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address.split("%")[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return (
        not (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
        and ip.is_global
    )


def fetch_preview(url: str, resolve: Callable[[str], list[str]], download: Callable[[str], bytes]) -> bytes:
    """The first 2048 bytes of a public web page, for a link preview.

    Only http and https addresses with a host name are fetched. `resolve(host)` returns the IP addresses the host name
    stands for; the page is fetched only when every one of them is a public address (not loopback, private, link-local,
    multicast, reserved or unspecified, IPv4 or IPv6). Anything else raises FetchRefused and `download` is not called."""
    try:
        parts = urlsplit(url.strip())
        host = parts.hostname
    except ValueError as error:
        raise FetchRefused("not a valid address") from error
    if parts.scheme.lower() not in ("http", "https") or not host:
        raise FetchRefused("only http and https addresses with a host")
    addresses = [host] if _looks_like_ip(host) else resolve(host)
    if not addresses or not all(_is_public(address) for address in addresses):
        raise FetchRefused("the address is not public")
    return download(url)[:2048]


def _looks_like_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.split("%")[0])
    except ValueError:
        return False
    return True


UNSAFE_NAME = re.compile(r"[^A-Za-z0-9 ._-]")


def content_disposition(filename: str) -> str:
    """The Content-Disposition header value for downloading a stored file under its original name.

    Returns `attachment; filename="<name>"`, where <name> keeps letters, digits, spaces, dots, dashes and underscores of the
    original name and has every other character replaced by "_". The result is always a single header line."""
    return f'attachment; filename="{UNSAFE_NAME.sub("_", filename)}"'


def tokens_match(given: str, expected: str) -> bool:
    """Whether an API token sent by a client equals the stored one, compared in constant time."""
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


def search_files(conn: sqlite3.Connection, owner: str, text: str) -> list[str]:
    """Names of `owner`'s files whose name contains `text` (literally, case-insensitive), sorted by name.

    Table: files(owner TEXT, name TEXT)."""
    literal = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = conn.execute(
        "SELECT name FROM files WHERE owner = ? AND name LIKE ? ESCAPE '\\' ORDER BY name",
        (owner, f"%{literal}%"),
    ).fetchall()
    return [row[0] for row in rows]


def _escape(value: str) -> str:
    out = []
    for ch in value:
        if ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 32 or ord(ch) == 127 or ch in (" ", " ", "\x85"):
            out.append(f"\\x{ord(ch):02x}" if ord(ch) < 256 else f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    return "".join(out)


def audit_line(user: str, action: str) -> str:
    """One line for the audit log: `user=<user> action=<action>`.

    The result is always exactly one line: control characters in either value are written as escapes (\\n, \\r, \\t or
    \\xNN), so a value can never start a forged log line."""
    return f"user={_escape(user)} action={_escape(action)}"


def reset_token() -> str:
    """A password-reset token: 32 characters from letters and digits, unpredictable to an attacker."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(32))
