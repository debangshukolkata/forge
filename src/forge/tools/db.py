"""Database tools (spec §9.5): db_schema, db_query (read-only), scratch_exec, db_request."""

from __future__ import annotations

import asyncio
from typing import Literal

import psycopg
from pydantic import Field

from forge.db.access import AccessLevel
from forge.db.checks import ServerRunCheck, add_check
from forge.db.connection import connect
from forge.db.introspect import describe, introspect
from forge.safety.sql_guard import SqlGuardError, check_read_only
from forge.tools.base import Tool, ToolArgs, ToolContext, ToolResult

NO_DB = ToolResult(
    ok=False, content="No database is configured for this workspace (LOCAL_PG_URL / DEV_PG_URL)."
)


def _readable_target(context: ToolContext, requested: str | None) -> str | None:
    db = context.db
    if db is None:
        return None
    candidates = [requested] if requested else [db.config.prefer, *db.targets]
    return next((n for n in candidates if n in db.reports and db.reports[n].level != AccessLevel.NONE), None)


class DbSchema(Tool):
    name = "db_schema"
    read_only = True
    description = (
        "Show tables, columns, keys and indexes of a live database (read-only). target: 'local' or 'dev' "
        "(default: the preferred reachable one); schema defaults to public."
    )

    class Args(ToolArgs):
        target: Literal["local", "dev"] | None = None
        schema_name: str = Field(default="public", description="Schema to describe.")
        table: str | None = None

    async def run(self, args: DbSchema.Args, context: ToolContext) -> ToolResult:
        name = _readable_target(context, args.target)
        if context.db is None or name is None:
            return (
                NO_DB
                if context.db is None
                else ToolResult(ok=False, content="No reachable database: " + context.db.status_line())
            )
        try:
            tables = await asyncio.to_thread(
                introspect, context.db.targets[name], context.db.secrets, args.schema_name, args.table
            )
        except (psycopg.Error, ValueError) as error:
            return ToolResult(ok=False, content=f"Introspection failed: {str(error).splitlines()[0]}")
        return ToolResult(ok=True, content=f"({name} database)\n" + describe(tables, context.db.deny_tables))


class DbQuery(Tool):
    name = "db_query"
    read_only = True
    description = (
        "Run a read-only query (SELECT/WITH/EXPLAIN/SHOW) on a real database. Rows are limited. "
        "Use EXPLAIN first for anything that could be heavy on a shared server."
    )

    class Args(ToolArgs):
        sql: str
        target: Literal["local", "dev"] | None = None
        limit: int = Field(default=100, ge=1, le=1000)

    def summary(self, args: DbQuery.Args) -> str:
        return f"db query: {' '.join(args.sql.split())[:100]}"

    async def run(self, args: DbQuery.Args, context: ToolContext) -> ToolResult:
        name = _readable_target(context, args.target)
        if context.db is None or name is None:
            return NO_DB if context.db is None else ToolResult(ok=False, content="No reachable database.")
        try:
            check_read_only(args.sql, context.db.deny_tables)
        except SqlGuardError as error:
            return ToolResult(ok=False, content=str(error))

        def run_query() -> tuple[list[str], list[tuple[object, ...]]]:
            assert context.db is not None
            with connect(context.db.targets[name], context.db.secrets, read_only=True) as connection:
                cursor = connection.execute(args.sql.encode("utf-8"))
                columns = [c.name for c in cursor.description or []]
                return columns, cursor.fetchmany(args.limit)

        try:
            columns, rows = await asyncio.to_thread(run_query)
        except psycopg.Error as error:
            return ToolResult(ok=False, content=f"Query failed: {str(error).splitlines()[0]}")
        return ToolResult(ok=True, content=_table(columns, rows, args.limit))


class ScratchExec(Tool):
    name = "scratch_exec"
    description = (
        "Run DDL/DML in this requirement's scratch schema only (search_path is set to it; use unqualified "
        "names). Every object you create is recorded and dropped at cleanup."
    )

    class Args(ToolArgs):
        sql: str

    def summary(self, args: ScratchExec.Args) -> str:
        return f"scratch sql: {' '.join(args.sql.split())[:100]}"

    async def run(self, args: ScratchExec.Args, context: ToolContext) -> ToolResult:
        if context.db is None or context.db.scratch is None:
            return ToolResult(
                ok=False,
                content="No scratch schema is available, so this SQL was NOT run and nothing was verified. "
                + (context.db.status_line() if context.db else "")
                + "\nHand it over instead: db_request with the exact SQL and a verification query "
                "(the user or their DBA runs it), and mark_server_run for any test that needs the database. "
                "Say plainly in your answer that it was not checked here.",
            )
        try:
            result = await asyncio.to_thread(context.db.scratch.execute, args.sql)
        except SqlGuardError as error:
            return ToolResult(ok=False, content=str(error))
        except psycopg.Error as error:
            return ToolResult(ok=False, content=f"SQL failed: {str(error).splitlines()[0]}")
        text = "; ".join(result.status)
        if result.columns:
            text += "\n" + _table(result.columns, result.rows, 200)
        if result.created:
            text += "\nCreated (will be dropped at cleanup): " + ", ".join(
                f"{k} {n}" for k, n in result.created
            )
        return ToolResult(ok=True, content=text)


class DbRequestTool(Tool):
    name = "db_request"
    read_only = True  # it only writes a request for a person; nothing runs
    description = (
        "When a database step needs rights Forge doesn't have (create the scratch schema or "
        "tables, grant access, "
        "install an extension), write it for the user or their DBA: exact idempotent SQL with a commented "
        "rollback, and a read-only verification query. Then keep working on tasks that don't "
        "depend on it; if "
        "the current task does, call task_update with status blocked and blocked_reason 'DBR-<n>'."
    )

    class Args(ToolArgs):
        title: str
        purpose: str
        sql: str
        verification_query: str
        who: Literal["you", "your DBA"] = "you"

    async def run(self, args: DbRequestTool.Args, context: ToolContext) -> ToolResult:
        if context.db is None:
            return NO_DB
        request = context.db.create_request(
            args.title, args.purpose, args.sql, args.verification_query, args.who
        )
        await context.emit("db_request_created", request.model_dump())
        await context.emit(
            "notice",
            {
                "kind": "db_request",
                "text": (
                    f"{request.id} created: {request.title}. See .forge/db_requests/{request.id}/REQUEST.md; "
                    f"when done, type /db done {request.id}"
                ),
            },
        )
        return ToolResult(ok=True, content=f"Created {request.id}. The user will run it and tell Forge.")


class MarkServerRun(Tool):
    name = "mark_server_run"
    read_only = True  # records a note; nothing runs
    description = (
        "Record DB-dependent tests you could not run here (no writable database, or a DB request that "
        "can't be done). They are delivered as server-run: listed as NOT run in the final report, with "
        "the exact command for someone who has access. Use only after trying the scratch schema."
    )

    class Args(ToolArgs):
        tests: str = Field(description="Test files or node ids, e.g. tests/test_policy_repo.py")
        reason: str
        command: str = Field(description="Exact command, run from the app folder with the venv active.")
        expected: str = Field(description="What a pass looks like.")

    async def run(self, args: MarkServerRun.Args, context: ToolContext) -> ToolResult:
        checks = add_check(context.workspace, ServerRunCheck(**args.model_dump()))
        return ToolResult(ok=True, content=f"Recorded as server-run ({len(checks)} in total).")


def _table(columns: list[str], rows: list[tuple[object, ...]], limit: int) -> str:
    if not columns:
        return "(no result set)"
    lines = [" | ".join(columns)]
    lines += [" | ".join("NULL" if v is None else str(v)[:80] for v in row) for row in rows]
    more = f"\n[showing at most {limit} rows]" if len(rows) >= limit else ""
    return "\n".join(lines) + more
