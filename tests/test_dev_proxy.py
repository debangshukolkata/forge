"""The relay between the copied application and the development database (D-610): deletes never reach the
server, writes are remembered, everything else passes. The local Postgres stands in for the development database
and psycopg for the application."""

# ruff: noqa: F811  (fixtures are imported from tests.test_db)

from __future__ import annotations

import asyncio
import struct
import threading
import uuid
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from forge.db.dev_proxy import DevProxy, DevProxyError, _Link, _ready, blocked_words, write_kind
from tests.test_db import _admin, admin_url, cleanup_schemas  # noqa: F401  (fixtures)


@pytest.mark.parametrize(
    ("sql", "words"),
    [
        ("SELECT * FROM agents", []),
        ("INSERT INTO notes (text) VALUES ('please delete this; drop it')", []),
        ("UPDATE agents SET name = 'x' -- delete later\n WHERE id = 1", []),
        ("SELECT deleted_at, dropdown FROM agents", []),  # part of a longer name is not the word
        ("DELETE FROM agents WHERE id = 1", ["delete"]),
        ("delete from agents", ["delete"]),
        ("BEGIN; TRUNCATE agents; COMMIT", ["truncate"]),
        ("DROP TABLE IF EXISTS agents", ["drop"]),
        ("WITH gone AS (DELETE FROM agents RETURNING id) SELECT * FROM gone", ["delete"]),
        ("EXPLAIN ANALYZE DELETE FROM agents", ["delete"]),
    ],
)
def test_which_statements_are_refused(sql: str, words: list[str]) -> None:
    assert blocked_words(sql) == words


@pytest.mark.parametrize(
    ("sql", "kind"),
    [
        ("SELECT 1", ""),
        ("  /* app */ insert into runs (a) values (1)", "INSERT"),
        ("UPDATE runs SET a = 2", "UPDATE"),
        ("WITH x AS (SELECT 1) UPDATE runs SET a = 2", "UPDATE"),
        ("WITH x AS (SELECT 1) SELECT * FROM x", ""),
        ("CREATE TABLE t (id int)", "CREATE"),
        ("BEGIN", ""),
    ],
)
def test_which_statements_count_as_writes(sql: str, kind: str) -> None:
    assert write_kind(sql) == kind


class Relay:
    """Runs the relay on its own event loop in a thread, as DebCraft's server loop does next to the application."""

    def __init__(self, url: str) -> None:
        parts = urlsplit(url)
        self.logged: list[tuple[str, dict[str, Any]]] = []
        self.proxy = DevProxy(
            parts.hostname or "127.0.0.1",
            parts.port or 5432,
            log=lambda kind, **fields: self.logged.append((kind, fields)),
        )
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()
        port = asyncio.run_coroutine_threadsafe(self.proxy.start(), self.loop).result(timeout=20)
        login = f"{parts.username}:{parts.password}@" if parts.password else f"{parts.username}@"
        self.url = urlunsplit(parts._replace(netloc=f"{login}127.0.0.1:{port}", query="sslmode=disable"))

    def stop(self) -> None:
        asyncio.run_coroutine_threadsafe(self.proxy.close(), self.loop).result(timeout=20)
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)


@pytest.fixture
def relay(admin_url: str) -> Iterator[Relay]:
    try:
        running = Relay(admin_url)
    except Exception as error:  # the local Postgres sometimes refuses a connection under a parallel run
        pytest.skip(f"local Postgres not reachable: {error}")
    yield running
    running.stop()


@pytest.fixture
def items(admin_url: str, cleanup_schemas: list[str]) -> str:
    name = f"forge_test_px_{uuid.uuid4().hex[:8]}"
    cleanup_schemas.append(name)
    with _admin(admin_url) as connection:
        connection.execute(f'CREATE SCHEMA "{name}"')
        connection.execute(f'CREATE TABLE "{name}".items (id serial PRIMARY KEY, name text)')
        connection.execute(f"INSERT INTO \"{name}\".items (name) VALUES ('a'), ('b'), ('c')")
    return f'"{name}".items'


def _count(admin_url: str, table: str) -> int:
    with _admin(admin_url) as connection:
        row = connection.execute(f"SELECT count(*) FROM {table}").fetchone()
    return int(row[0]) if row else -1


def _app(relay: Relay, **options: Any) -> psycopg.Connection[Any]:
    return psycopg.connect(relay.url, connect_timeout=10, **options)


@pytest.mark.pg
def test_reads_and_writes_pass_and_the_writes_are_remembered(
    relay: Relay, admin_url: str, items: str
) -> None:
    with _app(relay, autocommit=True) as app:
        assert app.execute(f"SELECT name FROM {items} ORDER BY id").fetchall() == [("a",), ("b",), ("c",)]
        app.execute(f"INSERT INTO {items} (name) VALUES ('d'), ('e')")  # no parameters: the simple protocol
        app.execute(
            f"UPDATE {items} SET name = %s WHERE id = %s", ("A", 1)
        )  # parameters: Parse, Bind, Execute
        app.execute(f"UPDATE {items} SET name = %s WHERE id = %s", ("B", 2))
        big = app.execute("SELECT repeat('x', 300000), generate_series(1, 2000)").fetchall()
        assert len(big) == 2000 and len(big[0][0]) == 300000  # messages larger than one read pass whole
    assert _count(admin_url, items) == 5
    activity = relay.proxy.activity
    assert activity.rows == {"INSERT": 2, "UPDATE": 2}
    report = activity.summary(only_new=True)
    assert "INSERT INTO" in report and "(x2)" in report and "Blocked" not in report
    assert "2 row(s) by INSERT" in report and "2 row(s) by UPDATE" in report
    assert "SELECT" not in report  # reads are not listed
    assert activity.summary(only_new=True) == ""  # nothing new since
    assert "INSERT INTO" in activity.summary(only_new=False)


@pytest.mark.pg
def test_a_delete_never_reaches_the_server_in_either_protocol(
    relay: Relay, admin_url: str, items: str
) -> None:
    with _app(relay, autocommit=True) as app:
        for statement, parameters in (
            (f"DELETE FROM {items} WHERE id = 1", None),
            (f"DELETE FROM {items} WHERE id = %s", (1,)),
            (f"TRUNCATE {items}", None),
            (f"DROP TABLE {items}", None),
            (f"WITH gone AS (DELETE FROM {items} RETURNING id) SELECT count(*) FROM gone", None),
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege) as refused:
                app.execute(statement, parameters)
            assert "not sent to the shared development database" in str(refused.value)
            # the connection is as usable as after any other database error
            assert app.execute(f"SELECT count(*) FROM {items}").fetchone() == (3,)
    assert _count(admin_url, items) == 3
    report = relay.proxy.activity.summary(only_new=True)
    assert "Blocked by DebCraft" in report and "DELETE FROM" in report and "TRUNCATE" in report
    assert "wrote to" not in report and relay.proxy.activity.rows == {}


@pytest.mark.pg
def test_a_refused_delete_fails_the_open_transaction(relay: Relay, admin_url: str, items: str) -> None:
    with _app(relay) as app:  # not autocommit: psycopg opens a transaction with the first statement
        app.execute(f"INSERT INTO {items} (name) VALUES (%s)", ("in the transaction",))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute(f"DELETE FROM {items} WHERE name = %s", ("a",))
        assert app.info.transaction_status == psycopg.pq.TransactionStatus.INERROR
        app.rollback()
        app.execute(f"INSERT INTO {items} (name) VALUES (%s)", ("after",))
        app.commit()
    with _admin(admin_url) as connection:
        names = [row[0] for row in connection.execute(f"SELECT name FROM {items} ORDER BY id").fetchall()]
    assert names == ["a", "b", "c", "after"]


@pytest.mark.pg
def test_batches_sent_ahead_get_the_refusal_at_the_right_place(
    relay: Relay, admin_url: str, items: str
) -> None:
    with _app(relay, autocommit=True) as app:
        with pytest.raises(psycopg.errors.InsufficientPrivilege), app.pipeline():
            first = app.execute(f"INSERT INTO {items} (name) VALUES (%s) RETURNING name", ("piped",))
            app.execute(f"DELETE FROM {items} WHERE id = %s", (1,))
        assert first.fetchone() == ("piped",)  # the statement before the refused one got its own answer
        assert app.execute("SELECT 1").fetchone() == (1,)
    assert _count(admin_url, items) == 4


@pytest.mark.pg
def test_several_connections_and_a_copy_pass(relay: Relay, admin_url: str, items: str) -> None:
    with _app(relay, autocommit=True) as one, _app(relay, autocommit=True) as two:
        with one.cursor().copy(f"COPY {items} (name) FROM STDIN") as copy:
            for index in range(50):
                copy.write_row((f"row {index}",))
        assert two.execute(f"SELECT count(*) FROM {items}").fetchone() == (53,)
    assert relay.proxy.activity.rows.get("COPY") == 50


def test_an_unreachable_database_is_reported_at_the_start() -> None:
    async def start() -> None:
        await DevProxy("127.0.0.1", 1).start()

    with pytest.raises(DevProxyError, match="did not answer"):
        asyncio.run(start())


def test_the_relay_counts_what_it_saw_and_writes_start_and_stop_to_the_log(relay: Relay, items: str) -> None:
    with _app(relay, autocommit=True) as app:
        app.execute(f"SELECT count(*) FROM {items}")
        app.execute(f"INSERT INTO {items} (name) VALUES (%s)", ("x",))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            app.execute(f"DELETE FROM {items}")
    stats = relay.proxy.stats()
    assert stats["connections"] == 1 and stats["refused_statements"] == 1 and stats["writing_statements"] == 1
    assert stats["messages"]["Q"] >= 2 and stats["rows"] == {"INSERT": 1} and stats["errors"] == {}
    relay.stop()
    kinds = [kind for kind, _ in relay.logged]
    assert kinds == ["relay_start", "relay_stop"]
    assert relay.logged[1][1]["refused_statements"] == 1
    assert "DELETE" not in str(relay.logged)  # numbers and kinds, never a statement
    relay.stop = lambda: None  # type: ignore[method-assign]  # already stopped: the fixture stops it again


def _message(kind: bytes, body: bytes = b"") -> bytes:
    return kind + struct.pack("!I", len(body) + 4) + body


PARSE_DELETE = _message(b"P", b"stmt\x00DELETE FROM t WHERE id = $1\x00\x00\x00")
FLUSH, SYNC, DESCRIBE = _message(b"H"), _message(b"S"), _message(b"D", b"Sstmt\x00")


def test_a_refused_parse_is_answered_at_the_flush_because_asyncpg_waits_for_it() -> None:
    """asyncpg sends Parse, Describe and Flush and no Sync until it has an answer: an error held back for a Sync
    that never comes froze the connection until its timeout (found with the real driver, D-615)."""
    proxy, link = DevProxy("127.0.0.1", 1), _Link()
    link.answered = 1  # the startup is over and nothing is owed to the application
    onward: list[bytes] = []
    back: list[bytes] = []
    for message in (PARSE_DELETE, DESCRIBE, FLUSH):
        proxy._inspect(link, message, onward, back)
    assert onward == [] and len(back) == 1 and back[0][:1] == b"E" and b"DebCraft" in back[0]
    proxy._inspect(link, SYNC, onward, back)  # the Sync goes on for its ReadyForQuery; no second error
    assert onward == [SYNC] and len(back) == 1 and not link.skipping and link.refusals == {}


async def test_the_error_waits_for_the_answers_still_owed_to_earlier_batches() -> None:
    proxy, link = DevProxy("127.0.0.1", 1), _Link()
    link.answered, link.asked = 1, 2  # one earlier batch is still owed its ReadyForQuery
    onward: list[bytes] = []
    back: list[bytes] = []
    for message in (PARSE_DELETE, DESCRIBE, FLUSH):
        proxy._inspect(link, message, onward, back)
    assert back == [] and link.flush_seen  # the earlier answer must come first

    class Application:
        def __init__(self) -> None:
            self.written: list[bytes] = []

        def write(self, data: bytes) -> None:
            self.written.append(data)

        async def drain(self) -> None:
            return None

    server = asyncio.StreamReader()
    server.feed_data(_ready(b"I"))
    server.feed_eof()
    application = Application()
    await proxy._from_server(link, server, application)  # type: ignore[arg-type]
    sent = b"".join(application.written)
    assert (
        sent.startswith(_ready(b"I")) and sent[len(_ready(b"I")) :][:1] == b"E"
    )  # its answer, then the error
    assert link.sent_early and not link.flush_seen
