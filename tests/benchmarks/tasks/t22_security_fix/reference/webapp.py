"""Request-handling helpers of a small web shop. Each function says what it is for; the web layer calls them with
values taken straight from the request (query string, cookie, path, form fields)."""

from __future__ import annotations

import ast
import base64
import binascii
import hashlib
import hmac
import html
import json
import operator
import os
import re
import secrets
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

# A configured key keeps sessions valid across restarts; without one a random key lives as long as the process.
_SESSION_KEY = os.environ.get("APP_SECRET", "").encode("utf-8") or secrets.token_bytes(32)


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT NOT NULL, price_cents INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, password_hash TEXT NOT NULL);
        """
    )


def search_products(conn: sqlite3.Connection, term: str) -> list[dict[str, Any]]:
    """Products whose name contains `term` (any case), ordered by id. `%` and `_` in the term are ordinary characters."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = conn.execute(
        "SELECT id, name, price_cents FROM products WHERE name LIKE ? ESCAPE '\\' ORDER BY id", (f"%{escaped}%",)
    )
    return [{"id": i, "name": n, "price_cents": p} for i, n, p in rows]


def read_public_file(base_dir: str, name: str) -> bytes:
    """Content of the file `name` inside the public folder `base_dir` (sub folders are fine).
    A name that points outside the folder raises ValueError; a missing file raises FileNotFoundError."""
    if not name or "\x00" in name:
        raise ValueError("bad file name")
    parts = re.split(r"[\\/]+", name)
    if name[0] in "/\\" or re.match(r"^[A-Za-z]:", name) or ".." in parts:
        raise ValueError("file name points outside the public folder")
    base = Path(base_dir).resolve()
    target = (base / name).resolve()  # resolves symlinks, so a link out of the folder is caught below
    try:
        target.relative_to(base)
    except ValueError:
        raise ValueError("file name points outside the public folder") from None
    return target.read_bytes()


def _sign(payload: str) -> str:
    return hmac.new(_SESSION_KEY, payload.encode("ascii"), hashlib.sha256).hexdigest()


def dump_session(data: dict[str, Any]) -> str:
    """The cookie text for a session dictionary (user name, roles, ...). The browser keeps it and sends it back."""
    raw = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return f"{payload}.{_sign(payload)}"


def load_session(cookie: str) -> dict[str, Any]:
    """The session dictionary from a cookie the browser sent back. A cookie that is malformed or that
    did not come from `dump_session` (forged or altered by the client) raises ValueError."""
    payload, dot, signature = cookie.partition(".") if isinstance(cookie, str) else ("", "", "")
    if not dot or not payload.isascii() or not hmac.compare_digest(_sign(payload).encode(), signature.encode("utf-8")):
        raise ValueError("invalid session cookie")
    try:
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, binascii.Error):
        raise ValueError("invalid session cookie") from None
    if not isinstance(data, dict):
        raise ValueError("invalid session cookie")
    return data


_BINARY = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos}
MAX_EXPONENT = 100


def _evaluate(node: ast.AST, depth: int = 0) -> int | float:
    if depth > 150:
        raise ValueError("expression is nested too deeply")
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value  # type: ignore[no-any-return]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_evaluate(node.operand, depth + 1))  # type: ignore[no-any-return]
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _evaluate(node.left, depth + 1), _evaluate(node.right, depth + 1)
        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise ValueError("exponent too large")
        return _BINARY[type(node.op)](left, right)  # type: ignore[no-any-return]
    raise ValueError("not an arithmetic expression")


def calculate(expression: str) -> int | float:
    """Value of an arithmetic expression typed into the price calculator: numbers, + - * / // % **, unary minus and
    parentheses. Anything else, or an expression that cannot be computed, raises ValueError. It must answer quickly
    for any input of up to 200 characters."""
    if not isinstance(expression, str) or len(expression) > 200:
        raise ValueError("expression too long")
    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _evaluate(tree.body)
    except (SyntaxError, ZeroDivisionError, OverflowError, RecursionError, MemoryError) as error:
        raise ValueError(f"cannot compute: {error}") from None
    if isinstance(result, float) and result != result:
        raise ValueError("not a number")
    return result


def _safe_url(url: str) -> bool:
    if not url or any(ord(char) < 32 or char in "\x7f" for char in url):
        return False
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.netloc)


def render_profile(name: str, bio: str, website: str = "") -> str:
    """HTML of a public profile box. `website` becomes a link when given."""
    page = f"<h1>Hello {html.escape(name)}</h1><p>{html.escape(bio)}</p>"
    if website and _safe_url(website):
        page += f'<a href="{html.escape(website.strip(), quote=True)}">website</a>'
    return page


def safe_redirect(target: str, default: str = "/") -> str:
    """Where to send the browser after login: the `next` value of the request if it is a place on this site, else `default`."""
    if (
        isinstance(target, str)
        and target.startswith("/")
        and not target.startswith("//")
        and "\\" not in target
        and not any(ord(char) < 32 or ord(char) == 127 for char in target)
        and not urlsplit(target).netloc
    ):
        return target
    return default
