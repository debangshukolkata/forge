from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from webapp import calculate, dump_session, init_db, load_session, read_public_file, render_profile, safe_redirect, search_products


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    conn.executemany("INSERT INTO products (name, price_cents) VALUES (?, ?)", [("Blue Mug", 800), ("Red mug", 750), ("Tea", 300)])
    return conn


def test_search_is_a_case_insensitive_substring_match() -> None:
    assert [p["name"] for p in search_products(make_db(), "MUG")] == ["Blue Mug", "Red mug"]
    assert search_products(make_db(), "zzz") == []


def test_read_public_file(tmp_path: Path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.txt").write_bytes(b"hello")
    assert read_public_file(str(tmp_path), "docs/a.txt") == b"hello"
    with pytest.raises(FileNotFoundError):
        read_public_file(str(tmp_path), "missing.txt")


def test_session_round_trip() -> None:
    data = {"user": "ana", "roles": ["admin"], "visits": 3}
    assert load_session(dump_session(data)) == data


def test_calculate_basics() -> None:
    assert calculate("2 + 3 * 4") == 14
    assert calculate("(2 + 3) * -4") == -20
    assert calculate("7 / 2") == 3.5


def test_render_profile() -> None:
    assert render_profile("Ana", "Likes tea") == "<h1>Hello Ana</h1><p>Likes tea</p>"


def test_safe_redirect_keeps_local_paths() -> None:
    assert safe_redirect("/orders?id=3") == "/orders?id=3"
    assert safe_redirect("") == "/"
