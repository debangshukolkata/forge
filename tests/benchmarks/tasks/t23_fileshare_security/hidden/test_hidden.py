from __future__ import annotations

import io
import random
import sqlite3
import zipfile
from pathlib import Path

import pytest

import fileshare
from fileshare import (
    MAX_ENTRIES,
    MAX_TOTAL_BYTES,
    FetchRefused,
    UploadError,
    audit_line,
    content_disposition,
    extract_upload,
    fetch_preview,
    reset_token,
    search_files,
    tokens_match,
)


def _zip(entries: dict[str, bytes], compression: int = zipfile.ZIP_STORED) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression) as archive:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name)  # a ZipInfo keeps a name such as ../x exactly as given
            info.compress_type = compression
            archive.writestr(info, data)
    return out.getvalue()


# --- extract_upload ---


def test_ordinary_archive_is_unpacked(tmp_path: Path) -> None:
    names = extract_upload(_zip({"a.txt": b"A", "docs/b.txt": b"B", "docs/": b""}), tmp_path / "out")
    assert names == ["a.txt", "docs/b.txt"]
    assert (tmp_path / "out" / "docs" / "b.txt").read_bytes() == b"B"


@pytest.mark.parametrize(
    "name",
    [
        "../escape.txt",
        "docs/../../escape.txt",
        "/abs/escape.txt",
        "..\\escape.txt",
        "C:\\escape.txt",
        "C:escape.txt",
        "\\\\server\\share\\x.txt",
    ],
)
def test_entries_that_leave_the_folder_are_refused_and_nothing_is_written(tmp_path: Path, name: str) -> None:
    destination = tmp_path / "inbox" / "out"
    destination.mkdir(parents=True)
    with pytest.raises(UploadError):
        extract_upload(_zip({"first.txt": b"1", name: b"evil"}), destination)
    assert not (destination / "first.txt").exists()  # nothing at all, not the entries before the bad one
    assert not list(tmp_path.rglob("escape.txt")) and not list(tmp_path.rglob("x.txt"))


def test_too_many_entries_are_refused(tmp_path: Path) -> None:
    with pytest.raises(UploadError):
        extract_upload(_zip({f"f{i}.txt": b"" for i in range(MAX_ENTRIES + 1)}), tmp_path)
    assert not list(tmp_path.iterdir())


def test_an_archive_too_big_when_unpacked_is_refused(tmp_path: Path) -> None:
    bomb = _zip({"zeros.bin": b"\0" * (MAX_TOTAL_BYTES + 1)}, zipfile.ZIP_DEFLATED)
    assert len(bomb) < 100_000
    with pytest.raises(UploadError):
        extract_upload(bomb, tmp_path)
    assert not (tmp_path / "zeros.bin").exists()


def test_not_a_zip_is_an_upload_error(tmp_path: Path) -> None:
    with pytest.raises(UploadError):
        extract_upload(b"plain text", tmp_path)


# --- fetch_preview ---


def _never(url: str) -> bytes:
    raise AssertionError("download must not be called")


@pytest.mark.parametrize(
    "addresses",
    [
        ["127.0.0.1"],
        ["10.1.2.3"],
        ["172.16.0.9"],
        ["192.168.1.1"],
        ["169.254.169.254"],
        ["0.0.0.0"],
        ["::1"],
        ["fe80::1"],
        ["fd00::5"],
        ["::ffff:127.0.0.1"],
        ["224.0.0.1"],
        ["93.184.215.14", "10.0.0.1"],
        [],
    ],
)
def test_hosts_that_resolve_to_inner_addresses_are_refused(addresses: list[str]) -> None:
    with pytest.raises(FetchRefused):
        fetch_preview("https://preview.example/", lambda host: addresses, _never)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://[::1]/",
        "http://169.254.169.254/latest/meta-data",
        "file:///etc/passwd",
        "gopher://example.org/",
        "https:///nohost",
        "ftp://example.org/x",
    ],
)
def test_inner_or_odd_addresses_are_refused_without_downloading(url: str) -> None:
    with pytest.raises(FetchRefused):
        fetch_preview(url, lambda host: ["93.184.215.14"], _never)


def test_a_public_page_is_fetched_and_cut() -> None:
    seen = []
    page = fetch_preview(
        "https://example.org/a",
        lambda host: ["93.184.215.14", "2606:2800:21f:cb07:6820:80da:af6b:8b2c"],
        lambda url: seen.append(url) or b"y" * 4000,
    )
    assert page == b"y" * 2048 and seen == ["https://example.org/a"]


# --- content_disposition ---


@pytest.mark.parametrize(
    "name",
    ['evil"; filename="x.exe', "a\r\nSet-Cookie: s=1", "a\nb", "a\\b.txt", "na\x00me.txt", "caf\u00e9.pdf"],
)
def test_the_header_is_one_line_with_only_safe_characters(name: str) -> None:
    value = content_disposition(name)
    assert value.startswith('attachment; filename="') and value.endswith('"')
    inner = value[len('attachment; filename="') : -1]
    assert all(ch.isascii() and (ch.isalnum() or ch in " ._-") for ch in inner), inner
    assert len(inner) == len(name)


def test_an_ordinary_name_is_kept() -> None:
    assert (
        content_disposition("report 2026_v2-final.pdf") == 'attachment; filename="report 2026_v2-final.pdf"'
    )


# --- tokens_match ---


def test_tokens_are_compared_in_constant_time(monkeypatch: pytest.MonkeyPatch) -> None:
    import hmac

    calls = []
    original = hmac.compare_digest

    def spy(a, b):  # type: ignore[no-untyped-def]
        calls.append((a, b))
        return original(a, b)

    monkeypatch.setattr(hmac, "compare_digest", spy)
    monkeypatch.setattr(fileshare, "hmac", hmac, raising=False)
    assert tokens_match("s3cret", "s3cret") and not tokens_match("s3cret", "s3creT")
    assert len(calls) == 2


def test_tokens_with_other_characters_do_not_crash() -> None:
    assert not tokens_match("caf\u00e9", "cafe") and tokens_match("caf\u00e9", "caf\u00e9")


# --- search_files ---


@pytest.fixture
def conn() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE files(owner TEXT, name TEXT)")
    db.executemany(
        "INSERT INTO files VALUES (?, ?)",
        [
            ("ana", "Plan.txt"),
            ("ana", "100% done.txt"),
            ("ana", "a_b.txt"),
            ("ana", "axb.txt"),
            ("ben", "secret plan.txt"),
            ("o'neil", "it's.txt"),
        ],
    )
    return db


def test_search_is_literal_and_per_owner(conn: sqlite3.Connection) -> None:
    assert search_files(conn, "ana", "plan") == ["Plan.txt"]
    assert search_files(conn, "ana", "%") == ["100% done.txt"]
    assert search_files(conn, "ana", "_") == ["a_b.txt"]
    assert search_files(conn, "o'neil", "'s") == ["it's.txt"]


@pytest.mark.parametrize("owner", ["ana' OR '1'='1", "x' UNION SELECT name FROM files --"])
def test_injection_through_the_owner_returns_nothing(conn: sqlite3.Connection, owner: str) -> None:
    assert search_files(conn, owner, "") == []


def test_injection_through_the_text_returns_nothing_of_others(conn: sqlite3.Connection) -> None:
    assert search_files(conn, "ana", "x' OR owner = 'ben") == []


# --- audit_line ---


@pytest.mark.parametrize(
    "user",
    [
        "ana\nuser=admin action=delete-all",
        "ana\r\nx",
        "ana\x1b[2J",
        "ana\u2028user=admin",
        "ana\x00",
        "ana\x85x",
    ],
)
def test_the_audit_line_is_always_one_line(user: str) -> None:
    line = audit_line(user, "login")
    assert len(line.splitlines()) == 1 and line.startswith("user=ana") and line.endswith(" action=login")
    assert not any(ord(ch) < 32 or ord(ch) == 127 for ch in line)


def test_escapes_are_the_documented_ones() -> None:
    assert audit_line("a\nb", "c\td") == "user=a\\nb action=c\\td"
    assert audit_line("a\x1bb", "x\ry") == "user=a\\x1bb action=x\\ry"


# --- reset_token ---


def test_reset_tokens_do_not_follow_the_random_module() -> None:
    random.seed(1234)
    first = reset_token()
    random.seed(1234)
    second = reset_token()
    assert first != second and len(first) == 32 and first.isalnum() and first.isascii()
