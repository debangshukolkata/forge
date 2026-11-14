"""Changes to the shared development database behind a red card (D-608): the statement guard (offline), the
tools against the local Postgres standing in for the development database, and the card's channel."""

# ruff: noqa: F811  (fixtures are imported from tests.test_db)

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

import httpx2
import psycopg
import pytest

from forge.config import PostgresConfig, Secrets
from forge.db.access import AccessLevel
from forge.db.dev_proxy import DevProxy
from forge.db.dev_write import LOG_FILE, MAX_ROWS
from forge.db.session import DbSession
from forge.engine.headless import HEADLESS_DANGER, auto_reply
from forge.engine.session_host import DANGER_DECLINE, SessionHost
from forge.protocol.events import Event, EventBus, EventType
from forge.protocol.inputs import Answer, SendMessage
from forge.safety.redact import Redactor
from forge.safety.sql_guard import SqlGuardError, check_dev_write
from forge.toolkit.base import ToolContext
from forge.tools.db import DbQuery, DbRequestTool, DbSchema
from forge.tools.deferred import GROUP_OF
from forge.tools.dev_db import DevDbActivity, DevDbUndo, DevDbWrite, UseDevDatabase
from forge.tools.registry import db_tools
from forge.workspace.workspace import Workspace
from tests.helpers import mocked_router
from tests.test_db import (  # noqa: F401  (fixtures)
    _admin,
    admin_url,
    cleanup_schemas,
    workspace,
)

# --- the guard (offline) -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sql", "kind", "table"),
    [
        ("INSERT INTO agents (name) VALUES ('a')", "insert", "agents"),
        ("insert into dev.tools (agent_id, comment) select 1, 'copy of a tool'", "insert", "dev.tools"),
        ("UPDATE agents SET name = 'b' WHERE id = 3;", "update", "agents"),
        (
            "UPDATE ONLY dev.agents SET note = 'delete this later; drop it' WHERE id = 3",
            "update",
            "dev.agents",
        ),
        ("UPDATE agents SET lock = true WHERE id IN (SELECT agent_id FROM tools)", "update", "agents"),
    ],
)
def test_one_insert_or_one_update_with_a_where_passes(sql: str, kind: str, table: str) -> None:
    write = check_dev_write(sql, deny_tables=["users"])
    assert (write.kind, write.table) == (kind, table)
    assert not write.text.endswith(";")


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM agents WHERE id = 3",
        "TRUNCATE agents",
        "DROP TABLE agents",
        "ALTER TABLE agents ADD COLUMN x int",
        "CREATE TABLE x (id int)",
        "SELECT * FROM agents",
        "UPDATE agents SET name = 'b'",  # no WHERE
        "UPDATE agents SET name = 'b' WHERE id = 1; DELETE FROM agents",
        "UPDATE agents SET name = 'b' WHERE id = 1; UPDATE agents SET name = 'c' WHERE id = 2",
        "WITH gone AS (DELETE FROM agents RETURNING id) INSERT INTO log SELECT id FROM gone",
        "INSERT INTO log SELECT id FROM (DELETE FROM agents RETURNING id) AS gone",
        "INSERT INTO agents (id) VALUES (1) ON CONFLICT (id) DO UPDATE SET name = 'x'",
        "MERGE INTO agents USING tools ON true WHEN MATCHED THEN DELETE",
        "UPDATE agents SET name = 'b' WHERE id = 1 RETURNING *",
        "UPDATE users SET password_hash = 'x' WHERE id = 1",  # credentials table
        "INSERT INTO agents (name) SELECT password_hash FROM users",
        "UPDATE pg_catalog.pg_class SET relname = 'x' WHERE oid = 1",
        "UPDATE agents SET name = pg_read_file('x') WHERE id = 1",
        "GRANT ALL ON agents TO public",
        "",
    ],
)
def test_everything_else_is_refused(sql: str) -> None:
    with pytest.raises(SqlGuardError):
        check_dev_write(sql, deny_tables=["users"])


def test_a_headless_run_never_approves_a_red_card() -> None:
    payload = {
        "id": "question-x-1",
        "danger": True,
        "recommended": None,
        "options": [{"label": "Change 1 row(s)"}, {"label": "Do not change"}],
    }
    event = Event(seq=1, ts="2026-11-13T10:00:00", type=EventType.QUESTION_ASKED, payload=payload)
    reply = auto_reply(event, auto_approve=True)
    assert isinstance(reply, Answer) and reply.choice is None and reply.text == HEADLESS_DANGER


async def test_the_hosts_red_card_is_approved_by_its_option_only() -> None:
    host = SessionHost(mocked_router(lambda request: httpx2.Response(500)), EventBus(redactor=Redactor()))

    async def ask() -> tuple[bool, str]:
        return await host._confirm_danger("Change 1 row(s)?", "what changes", "Change 1 row(s)")

    async def card_id() -> str:
        await asyncio.sleep(0)
        event = [e for e in host.bus.events_since(0) if e.type == EventType.QUESTION_ASKED][-1]
        assert event.payload["danger"] is True and event.payload["recommended"] is None
        assert [option["label"] for option in event.payload["options"]] == ["Change 1 row(s)", DANGER_DECLINE]
        return str(event.payload["id"])

    waiting = asyncio.create_task(ask())
    host.questions.resolve(Answer(question_id=await card_id(), choice="Change 1 row(s)"))
    assert await asyncio.wait_for(waiting, timeout=1) == (True, "")

    waiting = asyncio.create_task(ask())
    host.questions.resolve(Answer(question_id=await card_id(), choice=DANGER_DECLINE))
    assert (await asyncio.wait_for(waiting, timeout=1))[0] is False

    waiting = asyncio.create_task(ask())  # a typed message, even "yes", is not the click
    await card_id()
    await host.submit(SendMessage(text="yes go ahead"))
    assert await asyncio.wait_for(waiting, timeout=1) == (False, "yes go ahead")


def test_the_tools_wait_in_their_own_group_and_come_with_the_database_tools() -> None:
    assert GROUP_OF["dev_db_write"] == GROUP_OF["dev_db_undo"] == "dev_database"
    names = {"dev_db_write", "dev_db_undo", "use_dev_database", "dev_db_activity"}
    assert names <= {tool.name for tool in db_tools()} and all(
        GROUP_OF[name] == "dev_database" for name in names
    )


# --- against the local Postgres, standing in for the development database --------------------------------


class Card:
    """Stands in for the session host's red card: records what was shown and answers as told."""

    def __init__(self, approve: bool, before_answer: Any = None) -> None:
        self.approve = approve
        self.before_answer = before_answer
        self.shown: list[tuple[str, str, str]] = []

    async def __call__(self, question: str, details: str, approve_label: str) -> tuple[bool, str]:
        self.shown.append((question, details, approve_label))
        if self.before_answer is not None:
            self.before_answer()
        return self.approve, "" if self.approve else "not now"


@pytest.fixture
def dev_schema(admin_url: str, cleanup_schemas: list[str]) -> str:
    name = f"forge_test_dev_{uuid.uuid4().hex[:8]}"
    cleanup_schemas.append(name)
    with _admin(admin_url) as connection:
        connection.execute(f'CREATE SCHEMA "{name}"')
        connection.execute(
            f'CREATE TABLE "{name}".agents (id serial PRIMARY KEY, name text NOT NULL, settings jsonb, '
            "max_steps int, changed timestamptz)"
        )
        connection.execute(
            f'INSERT INTO "{name}".agents (name, settings, max_steps) VALUES '
            "('argo', '{\"model\": \"a\"}', 5), ('billing', NULL, 9), ('search', '{}', NULL)"
        )
        connection.execute(f'CREATE TABLE "{name}".notes (text text)')
        connection.execute(f"INSERT INTO \"{name}\".notes VALUES ('x')")
    return name


def _context(workspace: Workspace, admin_url: str, home: Path, card: Card | None) -> ToolContext:
    secrets = Secrets({"DEV_PG_URL": admin_url}, None)
    db = DbSession(PostgresConfig(), secrets, workspace, home, deny_tables=["users"])
    if db.detect()["dev"].level == AccessLevel.NONE:
        # The local Postgres sometimes refuses a connection while the whole suite runs in parallel.
        pytest.skip("local Postgres not reachable")
    context = ToolContext(workspace=workspace, db=db)
    context.confirm_danger = card
    return context


def _rows(admin_url: str, schema: str, query: str) -> list[tuple[Any, ...]]:
    with _admin(admin_url) as connection:
        return connection.execute(query.format(s=f'"{schema}"')).fetchall()


def _run(tool: Any, context: ToolContext, **arguments: Any) -> Any:
    return asyncio.run(tool.run(tool.Args(**arguments), context))


@pytest.mark.pg
def test_an_update_is_shown_with_old_and_new_values_then_committed_and_can_be_set_back(
    workspace: Workspace, admin_url: str, dev_schema: str, tmp_path: Path
) -> None:
    card = Card(approve=True)
    context = _context(workspace, admin_url, tmp_path / "home", card)
    result = _run(
        DevDbWrite(),
        context,
        sql=f"UPDATE {dev_schema}.agents SET max_steps = 20, settings = '{{\"model\": \"b\"}}' WHERE name = 'argo'",
        reason="The agent stops after 5 steps; the requirement needs 20.",
    )
    assert result.ok, result.content
    question, details, label = card.shown[0]
    assert "shared Development database" in question and label == "Change 1 row(s)"
    assert "**max_steps** `5` → `20`" in details and "needs 20" in details and "id=1" in details
    assert "name" not in details.split("will be changed")[1].split("DebCraft keeps")[0]  # unchanged column
    assert _rows(
        admin_url, dev_schema, "SELECT max_steps, settings->>'model' FROM {s}.agents WHERE id = 1"
    ) == [(20, "b")]
    assert "20" not in result.content.split("rows:")[0]  # counts and keys, not values

    log = [json.loads(line) for line in (workspace.forge_dir / LOG_FILE).read_text("utf-8").splitlines()]
    assert log[0]["id"] == 1 and log[0]["rows"][0]["old"]["max_steps"] == "5"

    undo_card = Card(approve=True)
    context.confirm_danger = undo_card
    undone = _run(DevDbUndo(), context, write_id=1)
    assert undone.ok, undone.content
    assert "`20` → `5`" in undo_card.shown[0][1]
    assert _rows(
        admin_url, dev_schema, "SELECT max_steps, settings->>'model' FROM {s}.agents WHERE id = 1"
    ) == [(5, "a")]
    again = _run(DevDbUndo(), context, write_id=1)
    assert not again.ok and "already set back" in again.content


@pytest.mark.pg
def test_nothing_changes_without_the_click(
    workspace: Workspace, admin_url: str, dev_schema: str, tmp_path: Path
) -> None:
    card = Card(approve=False)
    context = _context(workspace, admin_url, tmp_path / "home", card)
    result = _run(
        DevDbWrite(), context, sql=f"UPDATE {dev_schema}.agents SET max_steps = 1 WHERE id > 0", reason="test"
    )
    assert not result.ok and "did not approve" in result.content and "not now" in result.content
    assert len(card.shown) == 1 and "3 row(s)" in card.shown[0][0]
    assert _rows(admin_url, dev_schema, "SELECT max_steps FROM {s}.agents ORDER BY id") == [
        (5,),
        (9,),
        (None,),
    ]
    assert not (workspace.forge_dir / LOG_FILE).exists()

    context.confirm_danger = None  # a place where the user cannot be asked (a subagent)
    unasked = _run(
        DevDbWrite(), context, sql=f"UPDATE {dev_schema}.agents SET max_steps = 1 WHERE id = 1", reason="test"
    )
    assert not unasked.ok and "cannot be asked" in unasked.content
    assert _rows(admin_url, dev_schema, "SELECT max_steps FROM {s}.agents WHERE id = 1") == [(5,)]


@pytest.mark.pg
def test_a_refused_statement_never_reaches_the_card_or_the_database(
    workspace: Workspace, admin_url: str, dev_schema: str, tmp_path: Path
) -> None:
    card = Card(approve=True)
    context = _context(workspace, admin_url, tmp_path / "home", card)
    for sql in (
        f"DELETE FROM {dev_schema}.agents WHERE id = 1",
        f"UPDATE {dev_schema}.agents SET name = 'x'",
        f"UPDATE {dev_schema}.agents SET id = id + 100 WHERE id = 1",  # the key itself: could not be set back
        f"UPDATE {dev_schema}.notes SET text = 'y' WHERE text = 'x'",  # no primary key
        f"UPDATE {dev_schema}.agents SET name = 'x' WHERE id = 999",  # no rows
        f"UPDATE {dev_schema}.missing SET name = 'x' WHERE id = 1",
    ):
        result = _run(DevDbWrite(), context, sql=sql, reason="test")
        assert not result.ok and "Nothing was changed" in result.content, sql
    assert card.shown == []
    assert _rows(admin_url, dev_schema, "SELECT id, name FROM {s}.agents ORDER BY id") == [
        (1, "argo"),
        (2, "billing"),
        (3, "search"),
    ]


@pytest.mark.pg
def test_an_insert_is_added_after_approval_and_is_not_taken_out_again(
    workspace: Workspace, admin_url: str, dev_schema: str, tmp_path: Path
) -> None:
    card = Card(approve=True)
    context = _context(workspace, admin_url, tmp_path / "home", card)
    result = _run(
        DevDbWrite(),
        context,
        sql=f"INSERT INTO {dev_schema}.agents (name, max_steps) VALUES ('new 100% agent', 3)",
        reason="A test agent for the new tool.",
    )
    assert result.ok, result.content
    assert "will be added" in card.shown[0][1] and "`new 100% agent`" in card.shown[0][1]
    assert _rows(admin_url, dev_schema, "SELECT count(*) FROM {s}.agents WHERE name = 'new 100% agent'") == [
        (1,)
    ]
    undone = _run(DevDbUndo(), context, write_id=1)
    assert not undone.ok and "never deletes" in undone.content
    assert _rows(admin_url, dev_schema, "SELECT count(*) FROM {s}.agents") == [(4,)]


@pytest.mark.pg
def test_rows_changed_by_someone_else_stop_the_commit_and_the_undo(
    workspace: Workspace, admin_url: str, dev_schema: str, tmp_path: Path
) -> None:
    def someone_else() -> None:
        with _admin(admin_url) as connection:
            connection.execute(f'UPDATE "{dev_schema}".agents SET max_steps = 7 WHERE id = 1')

    card = Card(approve=True, before_answer=someone_else)  # the row changes while the card is open
    context = _context(workspace, admin_url, tmp_path / "home", card)
    sql = f"UPDATE {dev_schema}.agents SET max_steps = 20 WHERE id = 1"
    result = _run(DevDbWrite(), context, sql=sql, reason="test")
    assert not result.ok and "after the card was shown" in result.content
    assert _rows(admin_url, dev_schema, "SELECT max_steps FROM {s}.agents WHERE id = 1") == [(7,)]

    context.confirm_danger = Card(approve=True)
    assert _run(DevDbWrite(), context, sql=sql, reason="test").ok
    someone_else()  # after DebCraft's update somebody sets another value: the undo must not overwrite it
    undone = _run(DevDbUndo(), context, write_id=1)
    assert not undone.ok and "changed by someone" in undone.content
    assert _rows(admin_url, dev_schema, "SELECT max_steps FROM {s}.agents WHERE id = 1") == [(7,)]


@pytest.mark.pg
def test_a_statement_that_touches_too_many_rows_is_refused(
    workspace: Workspace, admin_url: str, dev_schema: str, tmp_path: Path
) -> None:
    with _admin(admin_url) as connection:
        connection.execute(
            f"INSERT INTO \"{dev_schema}\".agents (name) SELECT 'bulk' FROM generate_series(1, {MAX_ROWS + 1})"
        )
    card = Card(approve=True)
    context = _context(workspace, admin_url, tmp_path / "home", card)
    result = _run(
        DevDbWrite(),
        context,
        sql=f"UPDATE {dev_schema}.agents SET max_steps = 1 WHERE name = 'bulk'",
        reason="x",
    )
    assert not result.ok and "more than" in result.content and card.shown == []
    assert _rows(admin_url, dev_schema, "SELECT count(*) FROM {s}.agents WHERE max_steps = 1") == [(0,)]


# --- the copied application on the development database (D-610) --------------------------------------------


class Shell:
    def __init__(self) -> None:
        self.extra_env: dict[str, str] = {}


@pytest.mark.pg
async def test_the_copy_runs_on_the_development_database_only_after_the_card_and_through_the_relay(
    workspace: Workspace, admin_url: str, dev_schema: str, tmp_path: Path
) -> None:
    declined = Card(approve=False)
    context = _context(workspace, admin_url, tmp_path / "home", declined)
    context.shell = Shell()  # type: ignore[assignment]
    tool, arguments = UseDevDatabase(), {"variables": {"DATABASE_URL": "url", "DB_PORT": "port"}}
    refused = await tool.run(tool.Args(**arguments, reason="needs twenty tables"), context)
    assert not refused.ok and "did not approve" in refused.content
    assert context.db.dev_proxy is None and context.shell.extra_env == {}
    assert "needs twenty tables" in declined.shown[0][1] and "refused by DebCraft" in declined.shown[0][1]

    bad = await tool.run(tool.Args(variables={"DATABASE_URL": "schema"}), context)
    assert not bad.ok and "not one of" in bad.content and len(declined.shown) == 1  # no card for a wrong call

    card = Card(approve=True)
    context.confirm_danger = card
    try:
        result = await tool.run(tool.Args(**arguments, reason="needs twenty tables"), context)
        assert result.ok, result.content
        environment = context.shell.extra_env
        port = str(context.db.dev_proxy.local_port)
        assert environment["DB_PORT"] == port and "PGOPTIONS" not in environment
        assert (
            f"@127.0.0.1:{port}/" in environment["DATABASE_URL"]
            and "sslmode=disable" in environment["DATABASE_URL"]
        )
        assert environment["DATABASE_URL"] not in result.content and port not in result.content
        assert "DEVELOPMENT database" in context.db.status_line()

        again = await tool.run(tool.Args(variables={"DATABASE_URL": "url"}), context)
        assert again.ok and len(card.shown) == 1  # one card per session
        assert set(context.shell.extra_env) == {"DATABASE_URL"}

        def application() -> None:  # the copy of the application, with the settings DebCraft gave it
            with psycopg.connect(context.shell.extra_env["DATABASE_URL"], autocommit=True) as app:
                app.execute(f"UPDATE {dev_schema}.agents SET max_steps = %s WHERE name = %s", (11, "argo"))
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    app.execute(f"DELETE FROM {dev_schema}.agents WHERE name = 'billing'")

        await asyncio.to_thread(application)
        assert _rows(admin_url, dev_schema, "SELECT name, max_steps FROM {s}.agents ORDER BY id")[:2] == [
            ("argo", 11),
            ("billing", 9),
        ]
        seen = await DevDbActivity().run(DevDbActivity.Args(), context)
        assert (
            "UPDATE" in seen.content
            and "Blocked by DebCraft" in seen.content
            and "DELETE FROM" in seen.content
        )

        back = await tool.run(tool.Args(variables={}), context)
        assert back.ok and "UPDATE" in back.content and context.db.dev_proxy is None
        assert context.shell.extra_env == {}
    finally:
        if context.db.dev_proxy is not None:
            await context.db.dev_proxy.close()


async def test_the_user_is_told_after_the_turn_what_the_application_wrote() -> None:
    host = SessionHost(mocked_router(lambda request: httpx2.Response(500)), EventBus(redactor=Redactor()))
    proxy = DevProxy("127.0.0.1", 1)
    proxy.activity.note("INSERT INTO runs (agent) VALUES ($1)", "INSERT", blocked=False)
    proxy.activity.note("DELETE FROM sessions WHERE id = $1", "DELETE", blocked=True)
    proxy.activity.rows["INSERT"] = 1

    class Database:
        dev_proxy = proxy

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(SessionHost, "db", property(lambda self: Database()))
        await host._report_dev_writes()
        await host._report_dev_writes()  # nothing new: no second notice
    notices = [e.payload for e in host.bus.events_since(0) if e.payload.get("kind") == "dev_db_activity"]
    assert len(notices) == 1
    assert "INSERT INTO runs" in notices[0]["text"] and "NOT sent" in notices[0]["text"]


@pytest.mark.pg
def test_a_table_named_without_its_schema_is_found_by_the_tool(
    workspace: Workspace, admin_url: str, dev_schema: str, cleanup_schemas: list[str], tmp_path: Path
) -> None:
    """Live run 2026-11-13: the model wrote `UPDATE agents ...` for a table in the application's own schema, was
    told "not found" and handed the change to the user. Which schema holds a table is the tool's to look up."""
    only, twin = f"only_{uuid.uuid4().hex[:8]}", f"twin_{uuid.uuid4().hex[:8]}"
    other = f"forge_test_dev2_{uuid.uuid4().hex[:8]}"
    cleanup_schemas.append(other)
    with _admin(admin_url) as connection:
        connection.execute(f'CREATE SCHEMA "{other}"')
        connection.execute(f'CREATE TABLE "{dev_schema}".{only} (id int PRIMARY KEY, prompt text)')
        connection.execute(f"INSERT INTO \"{dev_schema}\".{only} VALUES (1, 'Always answer in English.')")
        for schema in (dev_schema, other):
            connection.execute(f'CREATE TABLE "{schema}".{twin} (id int PRIMARY KEY, prompt text)')
            connection.execute(f"INSERT INTO \"{schema}\".{twin} VALUES (1, 'x')")
    card = Card(approve=True)
    context = _context(workspace, admin_url, tmp_path / "home", card)
    result = _run(
        DevDbWrite(),
        context,
        sql=f"UPDATE {only} SET prompt = 'In the customer''s language.' WHERE id = 1",
        reason="x",
    )
    assert result.ok, result.content
    assert f"({dev_schema}.{only})" in card.shown[0][0] and f"{dev_schema}.{only}" in result.content
    assert _rows(admin_url, dev_schema, f"SELECT prompt FROM {{s}}.{only}") == [
        ("In the customer's language.",)
    ]
    assert _run(DevDbUndo(), context, write_id=1).ok
    assert _rows(admin_url, dev_schema, f"SELECT prompt FROM {{s}}.{only}") == [
        ("Always answer in English.",)
    ]

    several = _run(DevDbWrite(), context, sql=f"UPDATE {twin} SET prompt = 'y' WHERE id = 1", reason="x")
    assert (
        not several.ok and f"{dev_schema}.{twin}" in several.content and f"{other}.{twin}" in several.content
    )
    assert "with its schema" in several.content and len(card.shown) == 2  # no card for the ambiguous one
    named = _run(
        DevDbWrite(), context, sql=f"UPDATE {other}.{twin} SET prompt = 'y' WHERE id = 1", reason="x"
    )
    assert named.ok and _rows(admin_url, dev_schema, f"SELECT prompt FROM {{s}}.{twin}") == [("x",)]


@pytest.mark.pg
def test_the_read_tools_say_where_a_table_is_and_a_plain_change_is_not_handed_to_the_user(
    workspace: Workspace, admin_url: str, dev_schema: str, tmp_path: Path
) -> None:
    """Live run 2026-11-14: `agents` was in the application's schema; db_query said "does not exist", db_schema
    said "No tables found" ten times, and the model wrote a request for the user to run the UPDATE."""
    only = f"only_{uuid.uuid4().hex[:8]}"
    with _admin(admin_url) as connection:
        connection.execute(f'CREATE TABLE "{dev_schema}".{only} (id int PRIMARY KEY, prompt text)')
    context = _context(workspace, admin_url, tmp_path / "home", Card(approve=True))

    missing = _run(DbQuery(), context, sql=f"SELECT * FROM {only}")
    assert not missing.ok and f"It exists as: {dev_schema}.{only}" in missing.content
    found = _run(DbQuery(), context, sql=f"SELECT count(*) FROM {dev_schema}.{only}")
    assert found.ok

    wrong_schema = _run(DbSchema(), context, schema_name="public", table=only)
    assert f"It exists as: {dev_schema}.{only}" in wrong_schema.content
    empty = _run(DbSchema(), context, schema_name=f"forge_none_{uuid.uuid4().hex[:6]}")
    assert "Schemas with tables in the dev database" in empty.content and dev_schema in empty.content

    change = {"title": "t", "purpose": "p", "verification_query": "SELECT 1"}
    handed = _run(DbRequestTool(), context, sql=f"UPDATE {only} SET prompt = 'x' WHERE id = 1;", **change)
    assert not handed.ok and "dev_db_write" in handed.content and context.db.requests.all() == []
    allowed = _run(DbRequestTool(), context, sql="CREATE TABLE audit_log (id int)", **change)
    assert allowed.ok and len(context.db.requests.all()) == 1  # what DebCraft may not do is still a request
    context.confirm_danger = None  # nobody to approve: the request is the only way left
    assert _run(DbRequestTool(), context, sql=f"UPDATE {only} SET prompt = 'x' WHERE id = 1", **change).ok
