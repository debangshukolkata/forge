"""M7: the SQL guard (offline) and Forge's database layer against the local Postgres (marker pg).

The pg tests use LOCAL_PG_URL from the repo's .env and skip when that server isn't reachable. They only
touch schemas and roles named forge_test_* / forge_ws_*, and drop them afterwards.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest
from dotenv import dotenv_values

from forge.agent.state import Task
from forge.cli import _cleanup
from forge.config import PostgresConfig, Secrets
from forge.db.access import AccessLevel, detect
from forge.db.checks import ServerRunCheck, add_check
from forge.db.connection import DbTarget
from forge.db.requests import DbRequests
from forge.db.scratch import ScratchError, ScratchRegistry, ScratchSchema, scratch_name_for
from forge.db.session import DbSession
from forge.engine.events import EventBus
from forge.engine.session_host import SessionHost
from forge.safety.redact import Redactor
from forge.safety.sql_guard import SqlGuardError, check_read_only, check_scratch, split_statements
from forge.tools.base import ToolContext
from forge.tools.db import DbQuery, DbRequestTool, ScratchExec
from forge.workspace.create import create_workspace
from forge.workspace.output import build_output
from forge.workspace.workspace import Workspace
from tests.conftest import REPO_ROOT
from tests.helpers import mocked_router

# --- SQL guard (offline) ---------------------------------------------------------------------------


def test_statements_split_on_semicolons_outside_strings_comments_and_dollar_quotes() -> None:
    sql = """
        SELECT ';' AS a; -- a comment; with a semicolon
        CREATE FUNCTION f() RETURNS int AS $body$ SELECT 1; $body$ LANGUAGE sql;
        /* block; comment */ SELECT "odd;name" FROM t
    """
    assert len(split_statements(sql)) == 3


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM claims WHERE id = 1",
        "WITH x AS (SELECT 1) SELECT * FROM x",
        "EXPLAIN SELECT * FROM claims",
        "SELECT c.id, p.name FROM claims c JOIN policies p ON p.id = c.policy_id",
    ],
)
def test_read_only_queries_pass(sql: str) -> None:
    check_read_only(sql, deny_tables=[])


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM claims",
        "SELECT 1; DROP TABLE claims",
        "WITH gone AS (DELETE FROM claims RETURNING *) SELECT * FROM gone",
        "SELECT * FROM users",  # deny-listed credentials table
        "SELECT pg_read_file('postgresql.conf')",
        "EXPLAIN ANALYZE DELETE FROM claims",
    ],
)
def test_read_only_guard_rejects_writes_secrets_and_server_functions(sql: str) -> None:
    with pytest.raises(SqlGuardError):
        check_read_only(sql, deny_tables=["users"])


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE policies (id serial PRIMARY KEY, name text)",
        "INSERT INTO policies (name) VALUES ('a'); SELECT * FROM policies",
        "ALTER TABLE policies ADD COLUMN active boolean DEFAULT true",
        "CREATE INDEX ix_policies_name ON policies (name)",
        "SELECT p.id FROM policies p",
        "SELECT * FROM information_schema.columns WHERE table_name = 'policies'",
    ],
)
def test_scratch_guard_allows_work_inside_the_scratch_schema(sql: str) -> None:
    check_scratch(sql, "forge_ws", deny_tables=[])


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE public.policies (id int)",
        "DROP TABLE public.claims",
        "INSERT INTO other_schema.t VALUES (1)",
        "SET search_path = public",
        "GRANT SELECT ON policies TO someone",
        "DROP SCHEMA forge_ws CASCADE",
        "CREATE ROLE sneaky",
        "COPY policies FROM PROGRAM 'whoami'",
        "DO $$ BEGIN EXECUTE 'DROP TABLE public.claims'; END $$",
        "INSERT INTO pg_catalog.pg_class VALUES (1)",
        "SELECT * FROM users",
    ],
)
def test_scratch_guard_rejects_anything_outside_the_scratch_schema(sql: str) -> None:
    with pytest.raises(SqlGuardError):
        check_scratch(sql, "forge_ws", deny_tables=["users"])


# --- Local Postgres (marker pg) ------------------------------------------------------------------


@pytest.fixture(scope="module")
def admin_url() -> str:
    env_file = REPO_ROOT / ".env"
    url = dotenv_values(env_file).get("LOCAL_PG_URL") if env_file.exists() else None
    if not url:
        pytest.skip("LOCAL_PG_URL not configured in .env")
    try:
        with psycopg.connect(url, connect_timeout=3):
            pass
    except psycopg.Error:
        pytest.skip("local Postgres not reachable")
    return url


def _admin(url: str) -> psycopg.Connection[Any]:
    return psycopg.connect(url, autocommit=True)


def _schema_exists(url: str, schema: str) -> bool:
    with _admin(url) as connection:
        return (
            connection.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (schema,)).fetchone()
            is not None
        )


def _tables_in(url: str, schema: str) -> set[str]:
    with _admin(url) as connection:
        rows = connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = %s", (schema,)
        ).fetchall()
    return {r[0] for r in rows}


@pytest.fixture
def workspace(original_repo: Path, tmp_path: Path) -> Workspace:
    return create_workspace(original_repo, tmp_path / f"ws_{uuid.uuid4().hex[:6]}", "backend")


@pytest.fixture
def local_secrets(admin_url: str) -> Secrets:
    return Secrets({"LOCAL_PG_URL": admin_url}, None)


@pytest.fixture
def cleanup_schemas(admin_url: str) -> Iterator[list[str]]:
    names: list[str] = []
    yield names
    with _admin(admin_url) as connection:
        for name in names:
            connection.execute(f'DROP SCHEMA IF EXISTS "{name}" CASCADE')  # test cleanup only


LOCAL = DbTarget("local", "LOCAL_PG_URL")


@pytest.mark.pg
def test_admin_login_is_l3_and_a_read_only_role_is_l2(admin_url: str, cleanup_schemas: list[str]) -> None:
    schema = f"forge_test_{uuid.uuid4().hex[:6]}"
    role = f"forge_test_ro_{uuid.uuid4().hex[:6]}"
    cleanup_schemas.append(schema)
    with _admin(admin_url) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
        connection.execute(f"CREATE ROLE {role} LOGIN PASSWORD 'ro_test_pw'")  # check_secrets: fake
        connection.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO {role}')
    try:
        admin = detect(LOCAL, Secrets({"LOCAL_PG_URL": admin_url}, None), schema)
        assert admin.level == AccessLevel.WRITE and admin.scratch_exists

        parts = urlsplit(admin_url)
        ro_url = urlunsplit(parts._replace(netloc=f"{role}:ro_test_pw@{parts.hostname}:{parts.port or 5432}"))
        read_only = detect(LOCAL, Secrets({"LOCAL_PG_URL": ro_url}, None), schema)
        assert read_only.level == AccessLevel.READ_ONLY, read_only.line()
    finally:
        with _admin(admin_url) as connection:
            connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            connection.execute(f"DROP ROLE IF EXISTS {role}")


@pytest.mark.pg
def test_unreachable_server_is_l1_with_a_human_reason() -> None:
    url = "postgresql://nobody:x@127.0.0.1:1/none"  # check_secrets: fake
    report = detect(LOCAL, Secrets({"LOCAL_PG_URL": url}, None), "forge_x")
    assert report.level == AccessLevel.NONE
    assert "listening" in report.reason or "answer" in report.reason


@pytest.mark.pg
def test_scratch_lifecycle_records_objects_and_cleanup_drops_only_forges_own(
    workspace: Workspace, local_secrets: Secrets, admin_url: str, cleanup_schemas: list[str], tmp_path: Path
) -> None:
    schema = scratch_name_for(workspace)
    cleanup_schemas.append(schema)
    scratch = ScratchSchema(
        LOCAL, local_secrets, schema, ScratchRegistry(tmp_path / "home"), workspace, ["users"]
    )
    scratch.claim()
    scratch.create_schema()

    result = scratch.execute(
        "CREATE TABLE policies (id serial PRIMARY KEY, name text NOT NULL);"
        "INSERT INTO policies (name) VALUES ('home'), ('car');"
        "SELECT name FROM policies ORDER BY id"
    )
    assert result.rows == [("home",), ("car",)]
    assert ("table", "policies") in result.created
    with pytest.raises(SqlGuardError):
        scratch.execute("CREATE TABLE public.leak (id int)")
    assert "leak" not in _tables_in(admin_url, "public")

    with _admin(admin_url) as connection:  # someone else's table in the same schema
        connection.execute(f'CREATE TABLE "{schema}".not_forges (id int)')

    # Unqualified names resolve to the scratch schema only: public isn't on the search path.
    probe = f"forge_test_public_{uuid.uuid4().hex[:6]}"
    with _admin(admin_url) as connection:
        connection.execute(f"CREATE TABLE public.{probe} (id int)")
    try:
        with pytest.raises(psycopg.errors.UndefinedTable):
            scratch.execute(f"SELECT * FROM {probe}")
    finally:
        with _admin(admin_url) as connection:
            connection.execute(f"DROP TABLE public.{probe}")

    dropped = scratch.cleanup()
    assert "table policies" in dropped
    assert "not_forges" in _tables_in(admin_url, schema)  # not recorded, so not dropped
    assert dropped[-1].startswith(f"schema {schema} (kept")
    assert _schema_exists(admin_url, schema)


@pytest.mark.pg
def test_cleanup_drops_a_schema_forge_created_when_nothing_else_is_in_it(
    workspace: Workspace, local_secrets: Secrets, admin_url: str, cleanup_schemas: list[str], tmp_path: Path
) -> None:
    schema = scratch_name_for(workspace)
    cleanup_schemas.append(schema)
    scratch = ScratchSchema(LOCAL, local_secrets, schema, ScratchRegistry(tmp_path / "home"), workspace, [])
    scratch.create_schema()
    scratch.execute("CREATE TABLE t (id int); CREATE VIEW v AS SELECT id FROM t")
    dropped = scratch.cleanup()
    assert dropped == ["view v", "table t", f"schema {schema}"]
    assert not _schema_exists(admin_url, schema)


@pytest.mark.pg
def test_a_scratch_schema_is_locked_to_one_workspace(
    workspace: Workspace, local_secrets: Secrets, original_repo: Path, tmp_path: Path
) -> None:
    registry = ScratchRegistry(tmp_path / "home")
    ScratchSchema(LOCAL, local_secrets, "forge_shared", registry, workspace, []).claim()
    other = create_workspace(original_repo, tmp_path / "other_ws", "backend")
    with pytest.raises(ScratchError, match="in use by workspace"):
        ScratchSchema(LOCAL, local_secrets, "forge_shared", registry, other, []).claim()


@pytest.mark.pg
async def test_tools_query_read_only_and_scratch_env_reaches_commands(
    workspace: Workspace, local_secrets: Secrets, admin_url: str, cleanup_schemas: list[str], tmp_path: Path
) -> None:
    db = DbSession(PostgresConfig(), local_secrets, workspace, tmp_path / "home", deny_tables=["users"])
    cleanup_schemas.append(db.scratch_schema_name)
    reports = db.detect()
    assert reports["local"].level == AccessLevel.WRITE
    assert db.preferred_target() == "local"
    db.activate_scratch("local").create_schema()
    assert db.command_environment() == {"PGOPTIONS": f"-c search_path={db.scratch_schema_name}"}

    context = ToolContext(workspace=workspace, db=db)
    made = await ScratchExec().run(
        ScratchExec.Args(sql="CREATE TABLE items (id int); INSERT INTO items VALUES (7)"), context
    )
    assert made.ok, made.content
    read = await DbQuery().run(DbQuery.Args(sql=f"SELECT id FROM {db.scratch_schema_name}.items"), context)
    assert read.ok and "7" in read.content
    write = await DbQuery().run(DbQuery.Args(sql=f"DELETE FROM {db.scratch_schema_name}.items"), context)
    assert not write.ok

    with psycopg.connect(admin_url, options=db.command_environment()["PGOPTIONS"]) as app_connection:
        row = app_connection.execute("SELECT id FROM items").fetchone()  # what the app sees via PGOPTIONS
    assert row == (7,)
    assert db.scratch is not None
    db.scratch.cleanup()


@pytest.mark.pg
async def test_db_request_lifecycle_verifies_before_unblocking(
    workspace: Workspace, local_secrets: Secrets, admin_url: str, cleanup_schemas: list[str], tmp_path: Path
) -> None:
    db = DbSession(PostgresConfig(), local_secrets, workspace, tmp_path / "home", deny_tables=[])
    cleanup_schemas.append(db.scratch_schema_name)
    db.detect()
    context = ToolContext(workspace=workspace, db=db)
    result = await DbRequestTool().run(
        DbRequestTool.Args(
            title="Create the scratch schema",
            purpose="Tests need a place to create tables.",
            sql=f"CREATE SCHEMA IF NOT EXISTS {db.scratch_schema_name};\n-- rollback: DROP SCHEMA ...",
            verification_query=f"SELECT 1 FROM pg_namespace WHERE nspname = '{db.scratch_schema_name}'",
        ),
        context,
    )
    assert result.ok and "DBR-1" in result.content
    folder = workspace.forge_dir / "db_requests" / "DBR-1"
    assert (folder / "request.sql").exists() and "/db done DBR-1" in (folder / "REQUEST.md").read_text(
        "utf-8"
    )
    request = DbRequests(workspace).get("dbr-1")
    assert request is not None and request.status == "pending"

    ok, message = db.verify_request(request, None)
    assert not ok, "not run yet, so verification must fail"
    with _admin(admin_url) as connection:  # the user runs it
        connection.execute(f'CREATE SCHEMA "{db.scratch_schema_name}"')
    ok, message = db.verify_request(request, None)
    assert ok, message


# --- Output, unblocking and /db (offline unless marked pg) ---------------------------------------


def test_new_sql_scripts_go_into_db_changes_in_run_order(workspace: Workspace) -> None:
    sql = workspace.repo_dir / "backend" / "sql"
    (sql / "V005__add_index.sql").write_text("CREATE INDEX IF NOT EXISTS ix ON policies (name);\n", "utf-8")
    (sql / "V004__add_column.sql").write_text(
        "ALTER TABLE policies ADD COLUMN IF NOT EXISTS x int;\n", "utf-8"
    )
    add_check(
        workspace,
        ServerRunCheck(
            tests="tests/test_policy_repo.py",
            reason="no writable database",
            command="python -m pytest -q tests/test_policy_repo.py",
            expected="3 passed",
        ),
    )
    build_output(workspace)

    db_changes = (workspace.output_dir / "DB_CHANGES.sql").read_text("utf-8")
    assert db_changes.index("V004__add_column.sql") < db_changes.index("V005__add_index.sql")
    assert "ADD COLUMN IF NOT EXISTS x" in db_changes
    assert (workspace.output_dir / "backend" / "sql" / "V004__add_column.sql").exists()
    instructions = (workspace.output_dir / "COPY_INSTRUCTIONS.md").read_text("utf-8")
    assert "DB_CHANGES.sql" in instructions and "SERVER_RUN.md" in instructions
    assert "python -m pytest -q tests/test_policy_repo.py" in (
        workspace.output_dir / "SERVER_RUN.md"
    ).read_text("utf-8")


def _orchestrated_host(workspace: Workspace, secrets: Secrets | None) -> SessionHost:
    return SessionHost(
        mocked_router(lambda request: (_ for _ in ()).throw(AssertionError("no LLM call expected"))),
        EventBus(redactor=Redactor()),
        workspace=workspace,
        orchestrated=True,
        secrets=secrets,
    )


def test_resolving_a_db_request_unblocks_only_the_tasks_waiting_on_it(workspace: Workspace) -> None:
    """No phase to reset any more (D-131): unblocking makes the task pending again, and clears `exported`
    so the workspace is correctly seen as not-yet-resume-safe (needs_resume) until it's re-exported."""
    host = _orchestrated_host(workspace, None)
    assert host.orchestrator is not None
    state = host.orchestrator.state
    state.started, state.exported = True, True
    state.tasks = [
        Task(id="T1", title="tables", status="blocked", blocked_reason="needs DBR-1"),
        Task(id="T2", title="other", status="blocked", blocked_reason="DBR-2"),
    ]
    assert host.orchestrator.db_request_resolved("DBR-1", done=False, note="no DBA today")
    assert state.tasks[0].status == "pending" and "no DBA today" in state.tasks[0].description
    assert state.tasks[1].status == "blocked"
    assert state.exported is False and host.orchestrator.needs_resume
    assert not host.orchestrator.db_request_resolved("DBR-9", done=True, note="")


@pytest.mark.pg
async def test_db_done_verifies_then_continues_the_workflow(
    workspace: Workspace,
    local_secrets: Secrets,
    admin_url: str,
    cleanup_schemas: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _orchestrated_host(workspace, local_secrets)
    assert host.db is not None and host.orchestrator is not None
    cleanup_schemas.append(host.db.scratch_schema_name)
    await host.prepare_database()
    assert host.db.scratch is not None  # L3 locally: Forge created its scratch schema
    assert host.context_manager.pinned.get("database") is not None
    assert host.agent is not None and host.agent.context.shell is not None
    assert host.agent.context.shell.extra_env["PGOPTIONS"].endswith(host.db.scratch_schema_name)

    needed = f"forge_test_needed_{uuid.uuid4().hex[:6]}"
    cleanup_schemas.append(needed)
    request = host.db.create_request(
        "Create a schema",
        "test",
        f"CREATE SCHEMA {needed};",
        f"SELECT 1 FROM pg_namespace WHERE nspname = '{needed}'",
    )
    host.orchestrator.state.tasks = [Task(id="T1", title="x", status="blocked", blocked_reason=request.id)]
    continued: list[bool] = []

    async def fake_continue() -> None:
        continued.append(True)

    monkeypatch.setattr(host, "continue_work", fake_continue)
    first_seq = host.bus.last_seq

    await host._commands.handle(f"/db done {request.id}")
    assert host.db.requests.get(request.id).status == "pending"  # type: ignore[union-attr]
    assert not continued
    with _admin(admin_url) as connection:
        connection.execute(f'CREATE SCHEMA "{needed}"')
    await host._commands.handle(f"/db done {request.id}")
    assert host.db.requests.get(request.id).status == "done"  # type: ignore[union-attr]
    assert continued == [True]
    assert host.orchestrator.state.tasks[0].status == "pending"

    texts = [str(event.payload.get("text", "")) for event in host.bus.events_since(first_seq)]
    assert any("not verified yet" in t for t in texts)
    host.db.scratch.cleanup()


@pytest.mark.pg
def test_forge_cleanup_drops_only_the_workspaces_recorded_objects(
    workspace: Workspace,
    admin_url: str,
    isolated_forge_home: Path,
    cleanup_schemas: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (isolated_forge_home / ".env").write_text(f"LOCAL_PG_URL={admin_url}\n", encoding="utf-8")
    secrets = Secrets({"LOCAL_PG_URL": admin_url}, None)
    db = DbSession(PostgresConfig(), secrets, workspace, isolated_forge_home, deny_tables=[])
    cleanup_schemas.append(db.scratch_schema_name)
    db.activate_scratch("local").create_schema()
    assert db.scratch is not None
    db.scratch.execute("CREATE TABLE kept_by_registry (id int)")
    monkeypatch.setattr("builtins.input", lambda prompt: "y")

    assert _cleanup(workspace.root, yes=False) == 0
    assert not _schema_exists(admin_url, db.scratch_schema_name)
    assert ScratchRegistry(isolated_forge_home).load() == {}


@pytest.mark.pg
def test_cleanup_drops_referencing_tables_before_the_ones_they_reference(
    workspace: Workspace, local_secrets: Secrets, admin_url: str, cleanup_schemas: list[str], tmp_path: Path
) -> None:
    schema = scratch_name_for(workspace)
    cleanup_schemas.append(schema)
    registry = ScratchRegistry(tmp_path / "home")
    scratch = ScratchSchema(LOCAL, local_secrets, schema, registry, workspace, [])
    scratch.create_schema()
    scratch.execute(
        "CREATE TABLE policies (id serial PRIMARY KEY);"
        "CREATE TABLE claims (id serial PRIMARY KEY, policy_id int REFERENCES policies (id));"
        "CREATE INDEX ix_claims_policy ON claims (policy_id)"
    )
    dropped = scratch.cleanup()
    assert not any("not dropped" in d for d in dropped), dropped
    assert not _schema_exists(admin_url, schema)
    assert registry.load() == {}


# --- tables the code touches must exist in scratch (spec §9.5, D-107) ---


def test_code_tables_come_from_models_and_raw_sql(workspace: Workspace) -> None:
    from forge.db.table_check import code_tables

    code = code_tables(workspace)
    assert {"claims", "policies"} <= code.tables
    assert code.qualified_writes == []


def test_schema_qualified_writes_are_refused_on_the_shared_database(workspace: Workspace) -> None:
    from types import SimpleNamespace

    from forge.db.table_check import check_tables

    workspace.write_text(
        "backend/claims_app/repositories/archive_repository.py",
        "from sqlalchemy import text\n\n\ndef archive(session):\n"
        '    session.execute(text("INSERT INTO public.claims_archive SELECT * FROM claims"))\n',
    )
    shared = SimpleNamespace(scratch=SimpleNamespace(target=DbTarget("dev", "DEV_PG_URL"), schema="forge_x"))
    result = check_tables(workspace, shared)
    assert result is not None and result.refusal and "archive_repository.py" in result.refusal
    assert check_tables(workspace, SimpleNamespace(scratch=None)) is None


@pytest.mark.pg
def test_missing_scratch_tables_are_reported(
    workspace: Workspace, local_secrets: Secrets, admin_url: str, cleanup_schemas: list[str]
) -> None:
    from types import SimpleNamespace

    from forge.db.table_check import check_tables

    schema = f"forge_tc_{uuid.uuid4().hex[:6]}"
    cleanup_schemas.append(schema)
    with _admin(admin_url) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
        connection.execute(f'CREATE TABLE "{schema}".policies (id int)')
    db = SimpleNamespace(
        scratch=SimpleNamespace(target=LOCAL, secrets=local_secrets, schema=schema), deny_tables=[]
    )
    result = check_tables(workspace, db)
    assert result is not None and result.refusal is None
    assert "claims" in result.missing and "policies" not in result.missing
    assert "relation does not exist" in result.note(schema)
