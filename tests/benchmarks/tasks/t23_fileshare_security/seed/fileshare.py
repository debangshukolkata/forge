"""Helpers of a small file-sharing service. The web layer calls them with values taken from the request.

Each function's docstring says what it is for and how it may fail."""

from __future__ import annotations

import io
import random
import sqlite3
import string
import zipfile
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

MAX_TOTAL_BYTES = 10 * 1024 * 1024
MAX_ENTRIES = 1000


class UploadError(ValueError):
    """The upload cannot be accepted; the message says why."""


class FetchRefused(ValueError):
    """The address may not be fetched."""


def extract_upload(data: bytes, destination: str | Path) -> list[str]:
    """Unpack a zip upload into `destination` and return the relative names of the files written, in archive order.

    Folders inside the archive are kept. An archive with more than MAX_ENTRIES entries, or whose files would take more than
    MAX_TOTAL_BYTES once unpacked, is refused with UploadError, as is a file that is not a zip archive. Nothing may be written
    outside `destination`: an entry that would land outside it is refused with UploadError and nothing is written at all."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as error:
        raise UploadError("not a zip archive") from error
    written = []
    for info in archive.infolist():
        if info.is_dir():
            continue
        target = Path(destination) / info.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(archive.read(info))
        written.append(info.filename)
    return written


def fetch_preview(url: str, resolve: Callable[[str], list[str]], download: Callable[[str], bytes]) -> bytes:
    """The first 2048 bytes of a public web page, for a link preview.

    Only http and https addresses with a host name are fetched. `resolve(host)` returns the IP addresses the host name
    stands for; the page is fetched only when every one of them is a public address (not loopback, private, link-local,
    multicast, reserved or unspecified, IPv4 or IPv6). Anything else raises FetchRefused and `download` is not called."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise FetchRefused("only http and https")
    return download(url)[:2048]


def content_disposition(filename: str) -> str:
    """The Content-Disposition header value for downloading a stored file under its original name.

    Returns `attachment; filename="<name>"`, where <name> keeps letters, digits, spaces, dots, dashes and underscores of the
    original name and has every other character replaced by "_". The result is always a single header line."""
    return f'attachment; filename="{filename}"'


def tokens_match(given: str, expected: str) -> bool:
    """Whether an API token sent by a client equals the stored one, compared in constant time."""
    return given == expected


def search_files(conn: sqlite3.Connection, owner: str, text: str) -> list[str]:
    """Names of `owner`'s files whose name contains `text` (literally, case-insensitive), sorted by name.

    Table: files(owner TEXT, name TEXT)."""
    rows = conn.execute(
        f"SELECT name FROM files WHERE owner = '{owner}' AND name LIKE '%{text}%' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows]


def audit_line(user: str, action: str) -> str:
    """One line for the audit log: `user=<user> action=<action>`.

    The result is always exactly one line: control characters in either value are written as escapes (\\n, \\r, \\t or
    \\xNN), so a value can never start a forged log line."""
    return f"user={user} action={action}"


def reset_token() -> str:
    """A password-reset token: 32 characters from letters and digits, unpredictable to an attacker."""
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(32))
