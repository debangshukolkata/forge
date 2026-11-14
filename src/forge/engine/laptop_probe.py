"""The probe `forge laptop check` runs with the Python of the application, once per database driver (DV8, D-615).

It is a program of its own, not DebCraft code: it runs with the application's interpreter (`python -I -c`), so it can
only use what is installed there. It connects to the relay of DebCraft (never to the database directly), and per
driver it does what an application does: reads, a parameter query, a large answer, a TEMPORARY table with inserts and
an update, and two DELETEs (one plain, one with values) that the relay must refuse; after a refusal the connection
must still work. It prints one JSON line: the driver, its version and the steps with `ok` or `fail`.
Connection values come from the environment (`DEVCHK_*`) and are never printed.
"""

from __future__ import annotations

DRIVERS = ("psycopg", "psycopg2", "asyncpg", "sqlalchemy", "sqlalchemy_async")

PROBE = r'''
import asyncio, json, os, sys

driver = sys.argv[1]
H, P, U, W, D = (os.environ["DEVCHK_" + k] for k in ("HOST", "PORT", "USER", "PASSWORD", "DB"))
steps = []
TABLE = "forge_laptop_check"


def record(name, outcome, detail=""):
    steps.append([name, outcome, str(detail)[:140].replace(chr(10), " ")])


def step(name, action):
    try:
        detail = action()
        record(name, "ok", detail if detail is not None else "")
        return True
    except Exception as error:
        record(name, "fail", f"{type(error).__name__}: {error}")
        return False


async def astep(name, action):
    try:
        detail = await action()
        record(name, "ok", detail if detail is not None else "")
        return True
    except Exception as error:
        record(name, "fail", f"{type(error).__name__}: {error}")
        return False


def refused(action):
    try:
        action()
    except Exception as error:
        if "DebCraft" in str(error):
            return "refused by DebCraft"
        raise RuntimeError("an error, but not DebCraft's: " + str(error)[:90])
    raise RuntimeError("THE DELETE WAS NOT REFUSED")


async def arefused(action):
    try:
        await action()
    except Exception as error:
        if "DebCraft" in str(error):
            return "refused by DebCraft"
        raise RuntimeError("an error, but not DebCraft's: " + str(error)[:90])
    raise RuntimeError("THE DELETE WAS NOT REFUSED")


def finish(version):
    print(json.dumps({"driver": driver, "available": True, "version": version, "steps": steps}))


def missing(module):
    print(json.dumps({"driver": driver, "available": False, "why": str(module)[:100]}))


def sync_driver(connection, execute, fetch, commit):
    """The same steps for a DB-API connection; `execute(sql, params)` and `fetch()` are the driver's own."""
    step("select 1", lambda: (execute("SELECT 1", None), fetch())[1])
    step("parameter query", lambda: (execute("SELECT %s::int + 1", (41,)), fetch())[1])
    step("large answer", lambda: (execute("SELECT repeat('x', 300000)", None), len(fetch()[0][0]))[1])
    step("temp table", lambda: execute(f"CREATE TEMP TABLE {TABLE} (id int primary key, note text)", None))
    step("insert", lambda: execute(f"INSERT INTO {TABLE} VALUES (%s, %s), (%s, %s)", (1, "a", 2, "b")))
    step("update", lambda: execute(f"UPDATE {TABLE} SET note = %s WHERE id = %s", ("c", 1)))
    commit()
    step("delete refused (plain)", lambda: refused(lambda: execute(f"DELETE FROM {TABLE} WHERE id = 2", None)))
    step("delete refused (values)", lambda: refused(lambda: execute(f"DELETE FROM {TABLE} WHERE id = %s", (2,))))


def run_psycopg():
    try:
        import psycopg
    except ImportError:
        return missing("psycopg")
    holder = {}
    if not step("connect", lambda: holder.update(c=psycopg.connect(host=H, port=P, user=U, password=W, dbname=D, sslmode="disable", connect_timeout=20, autocommit=True))):
        return finish(psycopg.__version__)
    cursor = holder["c"].cursor()
    def execute(sql, params):
        cursor.execute(sql, params)
    sync_driver(holder["c"], execute, lambda: cursor.fetchall(), lambda: None)
    step("works after a refusal", lambda: (cursor.execute(f"SELECT count(*) FROM {TABLE}"), cursor.fetchone())[1])
    holder["c"].close()
    finish(psycopg.__version__)


def run_psycopg2():
    try:
        import psycopg2
    except ImportError:
        return missing("psycopg2")
    holder = {}
    def connect():
        holder["c"] = psycopg2.connect(host=H, port=P, user=U, password=W, dbname=D, sslmode="disable", connect_timeout=20)
        holder["c"].autocommit = True
    if not step("connect", connect):
        return finish(psycopg2.__version__)
    cursor = holder["c"].cursor()
    def execute(sql, params):
        cursor.execute(sql, params)
    def fetch():
        return cursor.fetchall()
    sync_driver(holder["c"], execute, fetch, lambda: None)
    step("works after a refusal", lambda: (cursor.execute(f"SELECT count(*) FROM {TABLE}"), cursor.fetchone())[1])
    holder["c"].close()
    finish(psycopg2.__version__)


def run_asyncpg():
    try:
        import asyncpg
    except ImportError:
        return missing("asyncpg")

    async def main():
        holder = {}
        async def connect():
            holder["c"] = await asyncpg.connect(host=H, port=int(P), user=U, password=W, database=D, ssl=False, timeout=20)
        if not await astep("connect", connect):
            return
        c = holder["c"]
        await astep("select 1", lambda: c.fetchval("SELECT 1"))
        await astep("parameter query", lambda: c.fetchval("SELECT $1::int + 1", 41))
        async def large():
            return len(await c.fetchval("SELECT repeat('x', 300000)"))
        await astep("large answer", large)
        await astep("temp table", lambda: c.execute(f"CREATE TEMP TABLE {TABLE} (id int primary key, note text)"))
        await astep("insert", lambda: c.execute(f"INSERT INTO {TABLE} VALUES ($1, $2), ($3, $4)", 1, "a", 2, "b"))
        await astep("update", lambda: c.execute(f"UPDATE {TABLE} SET note = $1 WHERE id = $2", "c", 1))
        await astep("delete refused (plain)", lambda: arefused(lambda: c.execute(f"DELETE FROM {TABLE} WHERE id = 2")))
        await astep("delete refused (values)", lambda: arefused(lambda: c.execute(f"DELETE FROM {TABLE} WHERE id = $1", 2)))
        await astep("works after a refusal", lambda: c.fetchval(f"SELECT count(*) FROM {TABLE}"))
        await c.close()

    asyncio.run(main())
    finish(asyncpg.__version__)


def sqlalchemy_url(sa, dialect):
    return sa.engine.URL.create(f"postgresql+{dialect}", username=U, password=W, host=H, port=int(P), database=D)


def run_sqlalchemy():
    try:
        import sqlalchemy as sa
    except ImportError:
        return missing("sqlalchemy")
    dialect = None
    for name in ("psycopg2", "psycopg"):
        try:
            __import__(name)
            dialect = name
            break
        except ImportError:
            continue
    if dialect is None:
        return missing("a synchronous driver for sqlalchemy (psycopg2 or psycopg)")
    engine = sa.create_engine(sqlalchemy_url(sa, dialect), pool_pre_ping=True, connect_args={"sslmode": "disable"})
    text = sa.text
    def in_transaction():
        with engine.connect() as c:
            c.execute(text("SELECT 1")).fetchall()
            c.execute(text("SELECT CAST(:n AS int) + 1"), {"n": 41}).fetchall()
            c.execute(text(f"CREATE TEMP TABLE {TABLE} (id int primary key, note text)"))
            c.execute(text(f"INSERT INTO {TABLE} VALUES (:a, :b), (:c, :d)"), {"a": 1, "b": "a", "c": 2, "d": "b"})
            c.execute(text(f"UPDATE {TABLE} SET note = :n WHERE id = :i"), {"n": "c", "i": 1})
            step("delete refused (plain)", lambda: refused(lambda: c.execute(text(f"DELETE FROM {TABLE} WHERE id = 2"))))
            c.rollback()
            step("delete refused (values)", lambda: refused(lambda: c.execute(text(f"DELETE FROM {TABLE} WHERE id = :i"), {"i": 2})))
    step("transaction with read, write and a refused delete", in_transaction)
    def after():
        with engine.connect() as c:
            return c.execute(text("SELECT 1")).fetchall()
    step("works after a refusal (new connection from the pool)", after)
    step("a large answer", lambda: len(engine.connect().execute(text("SELECT repeat('x', 300000)")).fetchone()[0]))
    engine.dispose()
    finish(f"{sa.__version__} + {dialect}")


def run_sqlalchemy_async():
    try:
        import sqlalchemy as sa
        from sqlalchemy.ext.asyncio import create_async_engine
        import asyncpg  # noqa: F401
    except ImportError as error:
        return missing(error)

    async def main():
        engine = create_async_engine(sqlalchemy_url(sa, "asyncpg"), connect_args={"ssl": False}, pool_pre_ping=True)
        text = sa.text
        async def read():
            async with engine.connect() as c:
                await c.execute(text("SELECT 1"))
                return (await c.execute(text("SELECT CAST(:n AS int) + 1"), {"n": 41})).fetchall()
        await astep("select and parameter query", read)
        async def write_and_refuse():
            async with engine.connect() as c:
                await c.execute(text(f"CREATE TEMP TABLE {TABLE} (id int primary key, note text)"))
                await c.execute(text(f"INSERT INTO {TABLE} VALUES (:a, :b)"), {"a": 1, "b": "a"})
                await c.execute(text(f"UPDATE {TABLE} SET note = :n WHERE id = :i"), {"n": "c", "i": 1})
                await arefused(lambda: c.execute(text(f"DELETE FROM {TABLE} WHERE id = :i"), {"i": 1}))
                await c.rollback()
        await astep("temp table, write, refused delete", write_and_refuse)
        async def after():
            async with engine.connect() as c:
                return (await c.execute(text("SELECT 1"))).fetchall()
        await astep("works after a refusal", after)
        await engine.dispose()

    asyncio.run(main())
    finish(sa.__version__ + " + asyncpg")


{"psycopg": run_psycopg, "psycopg2": run_psycopg2, "asyncpg": run_asyncpg, "sqlalchemy": run_sqlalchemy, "sqlalchemy_async": run_sqlalchemy_async}[driver]()
'''
