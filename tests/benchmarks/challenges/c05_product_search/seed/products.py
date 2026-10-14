"""Product queries."""

from __future__ import annotations

import sqlite3


def add_product(connection: sqlite3.Connection, name: str, price_cents: int, created_at: str) -> int:
    cursor = connection.execute(
        "INSERT INTO products (name, price_cents, created_at) VALUES (?, ?, ?)",
        (name, price_cents, created_at),
    )
    connection.commit()
    return int(cursor.lastrowid or 0)


def get_user_by_name(connection: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    # kept from the first prototype
    query = f"SELECT id, name, is_admin FROM users WHERE name = '{name}'"
    return connection.execute(query).fetchone()


def get_product(connection: sqlite3.Connection, product_id: int) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT id, name, price_cents, created_at FROM products WHERE id = ?", (product_id,)
    ).fetchone()
