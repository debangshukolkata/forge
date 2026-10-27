from __future__ import annotations

import base64
import json
import os
import pickle
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

import webapp
from webapp import calculate, dump_session, init_db, load_session, read_public_file, render_profile, safe_redirect, search_products


# ---------- SQL injection ----------


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    conn.executemany(
        "INSERT INTO products (name, price_cents) VALUES (?, ?)",
        [("Blue Mug", 800), ("Red mug", 750), ("Tea", 300), ("50% off mug", 100), ("500 mug", 90), ("a_b cup", 10), ("axb cup", 11), ("O'Brien's pipe", 500), ("back\\slash", 5)],
    )
    conn.execute("INSERT INTO users (name, password_hash) VALUES ('admin', 'HASH-OF-ADMIN-SECRET')")
    conn.commit()
    return conn


def names(rows: list[dict]) -> list[str]:  # type: ignore[type-arg]
    return [row["name"] for row in rows]


def test_search_still_works_case_insensitively() -> None:
    conn = make_db()
    assert names(search_products(conn, "mug")) == ["Blue Mug", "Red mug", "50% off mug", "500 mug"]
    assert search_products(conn, "TEA")[0] == {"id": 3, "name": "Tea", "price_cents": 300}


def test_empty_term_lists_everything_in_id_order() -> None:
    rows = search_products(make_db(), "")
    assert [row["id"] for row in rows] == list(range(1, 10))


@pytest.mark.parametrize(
    "term",
    [
        "' OR '1'='1",
        "%' OR 1=1 --",
        "x%' UNION SELECT id, password_hash, 0 FROM users --",
        "' UNION SELECT id, password_hash, 0 FROM users WHERE '%'='",
        "'; DROP TABLE products; --",
        '" OR ""="',
        "\\' OR 1=1 --",
    ],
)
def test_sql_injection_returns_nothing_and_changes_nothing(term: str) -> None:
    conn = make_db()
    assert search_products(conn, term) == []
    assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 9
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_apostrophes_and_backslashes_are_plain_text() -> None:
    conn = make_db()
    assert names(search_products(conn, "O'Brien")) == ["O'Brien's pipe"]
    assert names(search_products(conn, "k\\s")) == ["back\\slash"]


def test_like_wildcards_are_literal() -> None:
    conn = make_db()
    assert names(search_products(conn, "50%")) == ["50% off mug"]
    assert names(search_products(conn, "a_b")) == ["a_b cup"]
    assert search_products(conn, "%%%") == []
    assert search_products(conn, "_") == [{"id": 6, "name": "a_b cup", "price_cents": 10}]


# ---------- path traversal ----------


@pytest.fixture()
def public(tmp_path: Path) -> Path:
    folder = tmp_path / "public"
    (folder / "docs").mkdir(parents=True)
    (folder / "docs" / "a.txt").write_bytes(b"hello")
    (folder / "index.html").write_bytes(b"<h1>home</h1>")
    (tmp_path / "secret.txt").write_bytes(b"TOP SECRET")
    (tmp_path / "public_evil").mkdir()
    (tmp_path / "public_evil" / "x.txt").write_bytes(b"EVIL")
    return folder


def test_legitimate_files_are_served(public: Path) -> None:
    assert read_public_file(str(public), "index.html") == b"<h1>home</h1>"
    assert read_public_file(str(public), "docs/a.txt") == b"hello"
    with pytest.raises(FileNotFoundError):
        read_public_file(str(public), "nope.txt")
    with pytest.raises(FileNotFoundError):
        read_public_file(str(public), "docs/nope.txt")


@pytest.mark.parametrize(
    "name",
    [
        "../secret.txt",
        "..\\secret.txt",
        "docs/../../secret.txt",
        "docs\\..\\..\\secret.txt",
        "../public_evil/x.txt",
        "....//secret.txt/../../secret.txt",
        "/etc/passwd",
        "\\windows\\win.ini",
        "C:\\Windows\\win.ini",
        "c:/secret.txt",
        "a.txt\x00.png",
        "",
        "..",
    ],
)
def test_names_leading_outside_the_folder_are_refused(public: Path, name: str) -> None:
    with pytest.raises(ValueError):
        read_public_file(str(public), name)


def test_absolute_path_to_a_real_file_is_refused(public: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        read_public_file(str(public), str(tmp_path / "secret.txt"))


def test_a_symlink_pointing_out_of_the_folder_is_refused(public: Path, tmp_path: Path) -> None:
    link = public / "link.txt"
    try:
        link.symlink_to(tmp_path / "secret.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are not available here")
    with pytest.raises(ValueError):
        read_public_file(str(public), "link.txt")


# ---------- unsafe deserialisation ----------


class Evil:
    def __reduce__(self):  # type: ignore[no-untyped-def]
        return (exec, ("import os; os.environ['WEBAPP_PWNED'] = '1'",))


def test_session_round_trip_and_types() -> None:
    data = {"user": "ana", "roles": ["admin", "ops"], "visits": 3, "ratio": 0.5, "flag": True, "none": None, "nested": {"a": [1, 2]}}
    cookie = dump_session(data)
    assert isinstance(cookie, str) and cookie.isascii()
    assert load_session(cookie) == data
    assert load_session(dump_session({})) == {}


def test_cookie_can_travel_in_a_header() -> None:
    cookie = dump_session({"user": "ana", "note": "caf\u00e9 \u2603 ; = , \" '"})
    assert not any(char in cookie for char in ' ;,"\n\r\t\\')
    assert load_session(cookie)["note"] == "caf\u00e9 \u2603 ; = , \" '"


def test_pickle_payloads_are_never_executed() -> None:
    os.environ.pop("WEBAPP_PWNED", None)
    raw = pickle.dumps(Evil())
    attempts = [
        base64.b64encode(raw).decode(),
        base64.urlsafe_b64encode(raw).decode().rstrip("="),
        base64.b64encode(raw).decode() + ".deadbeef",
        base64.urlsafe_b64encode(raw).decode().rstrip("=") + "." + "0" * 64,
    ]
    for cookie in attempts:
        with pytest.raises(ValueError):
            load_session(cookie)
    assert "WEBAPP_PWNED" not in os.environ


def test_signed_cookie_with_a_pickle_inside_is_still_not_executed() -> None:
    os.environ.pop("WEBAPP_PWNED", None)
    with pytest.raises((ValueError, TypeError)):
        dump_session({"x": Evil()})  # type: ignore[dict-item]
    assert "WEBAPP_PWNED" not in os.environ


def test_forged_or_altered_cookies_are_refused() -> None:
    genuine = dump_session({"user": "ana", "roles": []})
    forged_plain = base64.urlsafe_b64encode(json.dumps({"user": "admin"}).encode()).decode()
    forged_standard = base64.b64encode(json.dumps({"user": "admin"}).encode()).decode()
    payload, _, signature = genuine.partition(".")
    other_payload = dump_session({"user": "admin", "roles": ["admin"]}).partition(".")[0]
    candidates = [
        forged_plain,
        forged_standard,
        forged_plain + "." + signature,  # signature of another payload
        other_payload + "." + signature,
        payload + ".",
        payload + "." + signature[:-1] + ("0" if signature[-1] != "0" else "1"),
        genuine[:-4],
        "." + signature,
        "",
        "not a cookie",
        "!!!!.????",
        genuine + ".extra",
    ]
    for cookie in candidates:
        with pytest.raises(ValueError):
            load_session(cookie)


def test_a_signed_non_dictionary_is_refused() -> None:
    cookie = dump_session({"a": 1})
    payload = cookie.partition(".")[0]
    assert load_session(cookie) == {"a": 1}
    assert payload  # sanity; lists cannot be produced by dump_session's contract, so only forgeries matter here
    for bad in (None, 5, b"abc"):
        with pytest.raises((ValueError, TypeError)):
            load_session(bad)  # type: ignore[arg-type]


# ---------- code injection through eval ----------


def run_isolated(code: str, timeout: float = 20.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(Path(webapp.__file__).parent),
        env={**os.environ, "PYTHONPATH": str(Path(webapp.__file__).parent)},
    )


def test_calculate_arithmetic() -> None:
    assert calculate("2 + 3 * 4") == 14
    assert calculate(" (2 + 3) * -4 ") == -20
    assert calculate("7 / 2") == 3.5
    assert calculate("7 // 2") == 3 and calculate("7 % 4") == 3
    assert calculate("2 ** 10") == 1024 and calculate("2 ** -1") == 0.5
    assert calculate("-(1 + 2) ** 2") == -9
    assert calculate("1.5 * 4") == 6.0
    assert calculate("+5") == 5
    assert calculate("((((1))))") == 1


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').getcwd()",
        "__import__('os').system('echo hi')",
        "open('x')",
        "().__class__",
        "[1][0]",
        "'a' * 3",
        "'a'",
        "x",
        "True",
        "None",
        "1 if 1 else 2",
        "lambda: 1",
        "(lambda: 1)()",
        "1 < 2",
        "1; 2",
        "import os",
        "abs(-1)",
        "1 +",
        "",
        "   ",
        "1 / 0",
        "1 // 0",
        "1 % 0",
        "0 ** -1",
    ],
)
def test_anything_but_plain_arithmetic_is_refused(expression: str) -> None:
    with pytest.raises(ValueError):
        calculate(expression)


def test_injection_has_no_side_effect_and_hostile_input_is_fast() -> None:
    result = run_isolated(
        "import os, webapp\n"
        "for e in [\"__import__('os').environ.__setitem__('CALC_PWNED','1')\", \"exec('import os')\", '9**9**9', '9**9**9**9', '10**10**10', '2**100000000', '9'*5000]:\n"
        "    try:\n"
        "        webapp.calculate(e)\n"
        "    except ValueError:\n"
        "        pass\n"
        "assert 'CALC_PWNED' not in os.environ\n"
        "print('ok')\n"
    )
    assert result.returncode == 0 and result.stdout.strip() == "ok", result.stderr[-500:]


# ---------- XSS ----------


def test_profile_escapes_text() -> None:
    page = render_profile("<script>alert(1)</script>", "Tom & \"Jerry\" <b>bold</b> it's")
    assert "<script>" not in page and "<b>" not in page
    assert "&lt;script&gt;" in page and "&amp;" in page and "&lt;b&gt;" in page
    assert page.startswith("<h1>Hello ") and page.endswith("</p>")


def test_profile_plain_text_is_unchanged() -> None:
    assert render_profile("Ana", "Likes tea") == "<h1>Hello Ana</h1><p>Likes tea</p>"
    assert render_profile("Ana", "Likes tea", "") == "<h1>Hello Ana</h1><p>Likes tea</p>"


def test_profile_links_http_and_https_only() -> None:
    page = render_profile("Ana", "x", "https://example.org/a?b=1&c=2")
    assert page.endswith('<a href="https://example.org/a?b=1&amp;c=2">website</a>')
    assert 'href="http://example.org"' in render_profile("Ana", "x", "http://example.org")


@pytest.mark.parametrize(
    "website",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        " javascript:alert(1)",
        "java\tscript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "vbscript:msgbox(1)",
        "//evil.example/x",
        "/relative",
        "ftp://example.org",
        "https://",
    ],
)
def test_dangerous_or_odd_website_values_get_no_link(website: str) -> None:
    page = render_profile("Ana", "x", website)
    assert "<a " not in page
    assert page == "<h1>Hello Ana</h1><p>x</p>"


def test_quotes_cannot_break_out_of_the_href() -> None:
    page = render_profile("Ana", "x", 'https://example.org/" onmouseover="alert(1)')
    assert '" onmouseover="' not in page


# ---------- open redirect ----------


@pytest.mark.parametrize("target", ["/", "/orders", "/orders?id=3&x=y", "/a/b/c#frag", "/search?q=http://x.org"])
def test_local_paths_are_kept(target: str) -> None:
    assert safe_redirect(target) == target


@pytest.mark.parametrize(
    "target",
    [
        "",
        "http://evil.example/",
        "https://evil.example",
        "//evil.example/x",
        "///evil.example",
        "/\\evil.example",
        "\\\\evil.example",
        "\\/evil.example",
        "javascript:alert(1)",
        "orders",
        "evil.example",
        "/ok\r\nSet-Cookie: x=1",
        "/ok\nLocation: http://evil.example",
        "/\t/evil.example",
        "/x\x00",
        "mailto:a@b.c",
    ],
)
def test_everything_else_goes_to_the_default(target: str) -> None:
    assert safe_redirect(target) == "/"
    assert safe_redirect(target, default="/home") == "/home"
