"""Copying tables into the scratch schema and pointing the application copy at it (D-568), on the local Postgres."""

# ruff: noqa: F811  (fixtures are imported from tests.test_db)

from __future__ import annotations

import uuid
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from forge.config import PostgresConfig, Secrets
from forge.db.copy_rows import copy_table
from forge.db.scratch import ScratchError, ScratchRegistry, ScratchSchema, scratch_name_for
from forge.db.session import DbSession
from forge.safety.sql_guard import SqlGuardError
from forge.workspace.workspace import Workspace
from tests.test_db import (  # noqa: F401  (fixtures)
    LOCAL,
    _admin,
    _tables_in,
    admin_url,
    cleanup_schemas,
    local_secrets,
    workspace,
)


@pytest.fixture
def source_schema(admin_url: str, cleanup_schemas: list[str]) -> str:
    """Stands in for the development database: a schema with an agents table and a table of their tools."""
    name = f"forge_test_src_{uuid.uuid4().hex[:8]}"
    cleanup_schemas.append(name)
    with _admin(admin_url) as connection:
        connection.execute(f'CREATE SCHEMA "{name}"')
        connection.execute(f"CREATE TYPE \"{name}\".tool_kind AS ENUM ('native', 'custom')")
        connection.execute(
            f'CREATE TABLE "{name}".tools (id serial PRIMARY KEY, agent_id int NOT NULL, name text NOT NULL, '
            f'kind "{name}".tool_kind NOT NULL, spec jsonb, tags text[], note text)'
        )
        connection.execute(
            f'INSERT INTO "{name}".tools (agent_id, name, kind, spec, tags, note) VALUES '
            "(1, 'list_deployments', 'native', '{\"path\": \"/api/v1/applications\", \"n\": [1, 2]}', '{argo,read}', "
            "E'line one\\nline\\ttwo'), "
            "(1, 'sync_app', 'native', NULL, NULL, NULL), "
            "(2, 'other_agent_tool', 'custom', '{}', '{}', 'x')"
        )
        connection.execute(f'CREATE TABLE "{name}".users (id int, password_hash text)')
    return name


def _scratch(
    workspace: Workspace, secrets: Secrets, home: Path, cleanup: list[str], deny: list[str]
) -> ScratchSchema:
    schema = scratch_name_for(workspace)
    cleanup.append(schema)
    scratch = ScratchSchema(LOCAL, secrets, schema, ScratchRegistry(home), workspace, deny)
    scratch.create_schema()
    return scratch


@pytest.mark.pg
def test_a_table_is_copied_with_its_shape_and_only_the_rows_asked_for(
    workspace: Workspace,
    local_secrets: Secrets,
    admin_url: str,
    cleanup_schemas: list[str],
    source_schema: str,
    tmp_path: Path,
) -> None:
    scratch = _scratch(workspace, local_secrets, tmp_path / "home", cleanup_schemas, ["users"])
    result = copy_table(scratch, LOCAL, source_schema, "tools", where="agent_id = 1")
    assert result.rows == 2 and result.as_text == ["kind"] and result.numbered == ["id"] and not result.capped
    assert "tools" in _tables_in(admin_url, scratch.schema)

    rows = scratch.execute("SELECT id, name, kind, spec->>'path', tags, note FROM tools ORDER BY id").rows
    assert rows[0] == (
        1,
        "list_deployments",
        "native",
        "/api/v1/applications",
        ["argo", "read"],
        "line one\nline\ttwo",
    )
    assert rows[1] == (2, "sync_app", "native", None, None, None)

    # The application can add a tool: the numbering goes on after the copied rows and the key still holds.
    scratch.execute("INSERT INTO tools (agent_id, name, kind) VALUES (1, 'deployment_names', 'custom')")
    assert scratch.execute("SELECT id FROM tools WHERE name = 'deployment_names'").rows == [(3,)]
    with pytest.raises(Exception, match="duplicate key"):
        scratch.execute("INSERT INTO tools (id, agent_id, name, kind) VALUES (1, 1, 'again', 'custom')")

    # The source is untouched, and a second copy replaces the first.
    with _admin(admin_url) as connection:
        assert connection.execute(f'SELECT count(*) FROM "{source_schema}".tools').fetchone() == (3,)
    again = copy_table(scratch, LOCAL, source_schema, "tools", limit=2)
    assert again.rows == 2 and again.capped
    assert scratch.execute("SELECT count(*) FROM tools").rows == [(2,)]
    assert "table tools" in scratch.cleanup()  # recorded, so cleanup drops it


@pytest.mark.pg
def test_credential_tables_and_anything_but_a_filter_are_refused(
    workspace: Workspace,
    local_secrets: Secrets,
    cleanup_schemas: list[str],
    source_schema: str,
    tmp_path: Path,
) -> None:
    scratch = _scratch(workspace, local_secrets, tmp_path / "home", cleanup_schemas, ["users"])
    with pytest.raises(ScratchError, match="credentials"):
        copy_table(scratch, LOCAL, source_schema, "users")
    with pytest.raises(SqlGuardError):
        copy_table(scratch, LOCAL, source_schema, "tools", where="true; DROP TABLE tools")
    with pytest.raises(SqlGuardError):
        copy_table(
            scratch, LOCAL, source_schema, "tools", where=f'id IN (SELECT id FROM "{source_schema}".users)'
        )
    with pytest.raises(ScratchError, match="not found"):
        copy_table(scratch, LOCAL, source_schema, "no_such_table")
    with pytest.raises(ValueError):
        copy_table(scratch, LOCAL, source_schema, 'tools"; DROP')


@pytest.mark.pg
def test_the_application_copy_gets_the_scratch_connection_under_its_own_setting_names(
    workspace: Workspace, local_secrets: Secrets, admin_url: str, cleanup_schemas: list[str], tmp_path: Path
) -> None:
    db = DbSession(PostgresConfig(), local_secrets, workspace, tmp_path / "home", [])
    assert db.command_environment() == {}
    db.detect()
    cleanup_schemas.append(db.scratch_schema_name)
    db.activate_scratch("local").create_schema()
    assert set(db.command_environment()) == {"PGOPTIONS"}

    db.set_app_variables(
        {
            "DATABASE_URL": "url:postgresql+psycopg2",
            "DB_HOST": "host",
            "DB_PASSWORD": "password",
            "DB_SCHEMA": "schema",
        }
    )
    environment = db.command_environment()
    parsed = urlsplit(admin_url)
    assert (
        environment["DATABASE_URL"].startswith("postgresql+psycopg2://")
        and parsed.hostname in environment["DATABASE_URL"]
    )
    assert environment["DB_HOST"] == parsed.hostname and environment["DB_SCHEMA"] == db.scratch_schema_name
    assert environment["DB_PASSWORD"] and "PGOPTIONS" in environment
    stored = (workspace.forge_dir / "db_app_env.json").read_text(encoding="utf-8")
    assert (
        "DB_PASSWORD" in stored and environment["DB_PASSWORD"] not in stored
    )  # names are kept, values never

    # A reopened session finds the mapping again.
    reopened = DbSession(PostgresConfig(), local_secrets, workspace, tmp_path / "home", [])
    reopened.detect()
    reopened.activate_scratch("local")
    assert reopened.command_environment()["DB_HOST"] == parsed.hostname

    with pytest.raises(ValueError):
        db.set_app_variables({"DB_HOST": "hostname"})
    with pytest.raises(ValueError):
        db.set_app_variables({"BAD NAME": "host"})
    db.set_app_variables({})
    assert set(db.command_environment()) == {"PGOPTIONS"}
