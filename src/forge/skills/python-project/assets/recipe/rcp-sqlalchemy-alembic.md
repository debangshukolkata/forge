---
id: rcp-sqlalchemy-alembic
type: recipe
title: SQLAlchemy 2.0 and Alembic migrations
summary: "Engine and session, typed declarative models, select() queries, loading strategies, transactions and migrations safe on live data."
moods: [robust, clean]
products: [database layer, backend, web app]
tags: [sqlalchemy, alembic, orm, migrations, transactions, n+1]
density: any
dependencies: [sqlalchemy, alembic]
licence: original
source: authored for DebCraft (python recipes, 2026-10-27)
tested: not executed (sqlalchemy and alembic are not installed in the build venv); follows the documented SQLAlchemy 2.0 API
---

## SQLAlchemy 2.0 and Alembic migrations

Rules:
- Use the 2.0 style only: `DeclarativeBase`, `Mapped[...]` / `mapped_column`, `select()` with `session.execute` or
  `session.scalars`. The old `session.query()` and untyped `Column` belong to code you are migrating.
- One `Engine` per process (created once, from a URL in the environment, `pool_pre_ping=True`); a short-lived `Session`
  per unit of work (a request, a job), always closed. Never share a session between threads.
- The transaction is the unit: `with Session(engine) as session, session.begin():` commits on success and rolls back on
  an exception. Do not call `commit()` inside helper functions; the caller owns the boundary.
- Relationships: default lazy loading causes N+1. Choose per query: `selectinload` for collections, `joinedload` for
  many-to-one, `raiseload("*")` in tests or hot paths to make accidental lazy loads fail.
- Put constraints in the database (`unique`, `nullable=False`, foreign keys, check constraints, indexes on filter columns),
  and name them with a `MetaData(naming_convention=...)` so Alembic can drop them later.
- Never build SQL by string formatting; pass values as bound parameters.

Worked example:

```python
from datetime import datetime
from sqlalchemy import ForeignKey, MetaData, String, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, selectinload, Session


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Author(Base):
    __tablename__ = "author"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    books: Mapped[list["Book"]] = relationship(back_populates="author", cascade="all, delete-orphan")


class Book(Base):
    __tablename__ = "book"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    author_id: Mapped[int] = mapped_column(ForeignKey("author.id"), index=True)
    published: Mapped[datetime | None] = mapped_column(default=None)
    author: Mapped[Author] = relationship(back_populates="books")


engine = create_engine("sqlite:///library.db", pool_pre_ping=True)  # URL from the environment in real code


def add_author_with_books(name: str, titles: list[str]) -> int:
    with Session(engine) as session, session.begin():  # commit or roll back as one unit
        author = Author(name=name, books=[Book(title=title) for title in titles])
        session.add(author)
        session.flush()  # assigns author.id without committing
        return author.id


def authors_with_book_counts(minimum: int) -> list[tuple[str, int]]:
    count = func.count(Book.id)
    statement = (
        select(Author.name, count)
        .join(Author.books)
        .group_by(Author.id)
        .having(count >= minimum)
        .order_by(count.desc())
    )
    with Session(engine) as session:
        return [(row.name, row[1]) for row in session.execute(statement)]


def titles_by_author() -> dict[str, list[str]]:
    statement = select(Author).options(selectinload(Author.books))  # two queries total, not 1 + N
    with Session(engine) as session:
        return {a.name: [b.title for b in a.books] for a in session.scalars(statement)}
```

Alembic:
- `alembic init migrations`, point `env.py` at `Base.metadata` and the URL from the environment, set
  `compare_type=True`. `alembic revision --autogenerate -m "add book.published"` drafts a migration.
- Always read the draft. Autogenerate misses renames (shows drop plus add, which loses data), server defaults, check
  constraints and data changes. Fix by hand, then run `alembic upgrade head` on a copy of production data.
- Safe on live data: expand, migrate, contract. Add the new nullable column, deploy code that writes both, backfill in
  batches, add the `NOT NULL` or drop the old column in a later release. Build big indexes concurrently (PostgreSQL:
  `postgresql_concurrently=True` inside an autocommit block). Write a working `downgrade()` or say it is one-way.
- One head only; resolve branches with `alembic merge`. In SQLite use `batch_alter_table` for column changes.

Gotchas:
- Objects are expired after commit by default, so attribute access starts a query; use `expire_on_commit=False` when you
  return ORM objects past the session, or return plain values as above.
- `session.add` inside a loop followed by one query per item is slow; use `session.add_all` and bulk `insert()`.
- Tests: use an in-memory SQLite or a throwaway schema, create tables from the metadata, and also run `upgrade head`
  once in CI so the migrations themselves are tested.
