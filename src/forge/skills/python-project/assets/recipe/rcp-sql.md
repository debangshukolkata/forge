---
id: rcp-sql
type: recipe
title: SQL from Python safely
summary: "Parameterised queries, transactions, sqlite for tests, and where migrations live."
moods: [secure, robust]
products: [database, backend, data]
tags: [sql, sqlite, sqlalchemy, injection, transactions]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-13)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## SQL from Python safely

Rules: never build SQL with f-strings or `%` formatting: pass values as parameters (`?` in sqlite3, `%s` in psycopg,
`:name` in SQLAlchemy `text()`); one transaction per business operation (commit or roll back together); close connections
(`with`); keep SQL in one data layer; schema changes go through migrations (Alembic, or numbered `.sql` files applied in
order), never ad-hoc `ALTER` in application code; for tests use a throwaway sqlite file or in-memory database.

```python
# runnable
import sqlite3
from contextlib import closing


def init(db: sqlite3.Connection) -> None:
    db.execute("CREATE TABLE IF NOT EXISTS stock (sku TEXT PRIMARY KEY, qty INTEGER NOT NULL CHECK (qty >= 0))")


def move(db: sqlite3.Connection, source: str, target: str, qty: int) -> None:
    """Both updates happen or neither does."""
    with db:  # commits on success, rolls back if an exception escapes
        db.execute("UPDATE stock SET qty = qty - ? WHERE sku = ?", (qty, source))
        db.execute("UPDATE stock SET qty = qty + ? WHERE sku = ?", (qty, target))


with closing(sqlite3.connect(":memory:")) as db:
    init(db)
    db.executemany("INSERT INTO stock VALUES (?, ?)", [("A", 5), ("B", 0)])
    move(db, "A", "B", 3)
    assert dict(db.execute("SELECT sku, qty FROM stock")) == {"A": 2, "B": 3}
    try:
        move(db, "A", "B", 9)  # would make A negative: the CHECK fails, nothing changes
    except sqlite3.IntegrityError:
        pass
    assert dict(db.execute("SELECT sku, qty FROM stock")) == {"A": 2, "B": 3}
    hostile = "A'; DROP TABLE stock; --"
    assert db.execute("SELECT qty FROM stock WHERE sku = ?", (hostile,)).fetchone() is None  # treated as data
```

Add an index for every column you filter or join on in hot queries; look at `EXPLAIN` before guessing. Fetch only the
columns and rows you need; never `SELECT *` into application code. Money is an integer of the smallest unit or `Decimal`,
never float.
