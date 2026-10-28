import io
import sqlite3
import zipfile

from fileshare import (
    audit_line,
    content_disposition,
    extract_upload,
    fetch_preview,
    reset_token,
    search_files,
    tokens_match,
)


def _zip(entries: dict[str, bytes]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return out.getvalue()


def test_extract_upload(tmp_path):
    names = extract_upload(_zip({"a.txt": b"A", "docs/b.txt": b"B"}), tmp_path)
    assert names == ["a.txt", "docs/b.txt"]
    assert (tmp_path / "docs" / "b.txt").read_bytes() == b"B"


def test_fetch_preview():
    page = fetch_preview("https://example.org/", lambda host: ["93.184.215.14"], lambda url: b"x" * 5000)
    assert page == b"x" * 2048


def test_content_disposition():
    assert content_disposition("report 2026.pdf") == 'attachment; filename="report 2026.pdf"'


def test_tokens_match():
    assert tokens_match("abc", "abc") and not tokens_match("abc", "abd")


def test_search_files():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE files(owner TEXT, name TEXT)")
    conn.executemany(
        "INSERT INTO files VALUES (?, ?)", [("ana", "Plan.txt"), ("ana", "notes.md"), ("ben", "plan-b.txt")]
    )
    assert search_files(conn, "ana", "plan") == ["Plan.txt"]


def test_audit_line():
    assert audit_line("ana", "download") == "user=ana action=download"


def test_reset_token():
    token = reset_token()
    assert len(token) == 32 and token.isalnum()
