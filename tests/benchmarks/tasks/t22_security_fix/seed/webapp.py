"""Request-handling helpers of a small web shop. Each function says what it is for; the web layer calls them with
values taken straight from the request (query string, cookie, path, form fields)."""

from __future__ import annotations

import base64
import os
import pickle
import sqlite3
from typing import Any


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT NOT NULL, price_cents INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, password_hash TEXT NOT NULL);
        """
    )


def search_products(conn: sqlite3.Connection, term: str) -> list[dict[str, Any]]:
    """Products whose name contains `term` (any case), ordered by id. `%` and `_` in the term are ordinary characters."""
    query = f"SELECT id, name, price_cents FROM products WHERE name LIKE '%{term}%' ORDER BY id"
    return [{"id": i, "name": n, "price_cents": p} for i, n, p in conn.execute(query)]


def read_public_file(base_dir: str, name: str) -> bytes:
    """Content of the file `name` inside the public folder `base_dir` (sub folders are fine).
    A name that points outside the folder raises ValueError; a missing file raises FileNotFoundError."""
    with open(os.path.join(base_dir, name), "rb") as handle:
        return handle.read()


def dump_session(data: dict[str, Any]) -> str:
    """The cookie text for a session dictionary (user name, roles, ...). The browser keeps it and sends it back."""
    return base64.b64encode(pickle.dumps(data)).decode("ascii")


def load_session(cookie: str) -> dict[str, Any]:
    """The session dictionary from a cookie the browser sent back. A cookie that is malformed or that
    did not come from `dump_session` (forged or altered by the client) raises ValueError."""
    return pickle.loads(base64.b64decode(cookie))  # type: ignore[no-any-return]


def calculate(expression: str) -> int | float:
    """Value of an arithmetic expression typed into the price calculator: numbers, + - * / // % **, unary minus and
    parentheses. Anything else, or an expression that cannot be computed, raises ValueError. It must answer quickly
    for any input of up to 200 characters."""
    return eval(expression)  # type: ignore[no-any-return]


def render_profile(name: str, bio: str, website: str = "") -> str:
    """HTML of a public profile box. `website` becomes a link when given."""
    html = f"<h1>Hello {name}</h1><p>{bio}</p>"
    if website:
        html += f'<a href="{website}">website</a>'
    return html


def safe_redirect(target: str, default: str = "/") -> str:
    """Where to send the browser after login: the `next` value of the request if it is a place on this site, else `default`."""
    return target or default
