"""Database tools (spec §9.5): db_schema, db_query (read-only), scratch_exec, db_request."""

from __future__ import annotations

import asyncio
from typing import Literal

import psycopg
from pydantic import Field

from forge.db.access import AccessLevel
from forge.db.connection import connect
from forge.db.copy_rows import MAX_COPY_ROWS, copy_table
from forge.db.introspect import describe, introspect
from forge.db.scratch import ScratchError
from forge.safety.sql_guard import SqlGuardError, check_read_only
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.workspace.server_checks import ServerRunCheck, add_check

NO_DB = ToolResult(
    ok=False, content="No database is configured for this workspace (LOCAL_PG_URL / DEV_PG_URL)."
)


async def _ensure_checked(context: ToolContext) -> None:
    """The access check normally runs when a requirement starts; a chat question, a standalone (Mode B) project or a reopened one
    reaches these tools before that, and "not checked yet" then looks like "unreachable" although the drawer's test says connected."""
    db = context.db
    if db is None or db.reports:
        return
    try:
        await asyncio.to_thread(db.detect)
    except (psycopg.Error, OSError, ValueError):
        return  # the status line then still says what is wrong


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
        await _ensure_checked(context)
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
        await _ensure_checked(context)
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
        "When a database step needs rights DebCraft doesn't have (create the scratch schema or "
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
        return ToolResult(ok=True, content=f"Created {request.id}. The user will run it and tell DebCraft.")


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


class DbCopyTable(Tool):
    name = "db_copy_table"
    description = (
        "Copy a table (its columns, primary key and rows) from a database you may only read into your scratch "
        "schema, so a copy of the application can run on its own data without touching the real database. "
        "`table`: `schema.table` or a table of `public`. `where`: an optional SQL condition to copy only the rows "
        "you need (for example `agent_id = 12`). `limit`: at most this many rows (default 5000). The rows go "
        "straight from one database to the other; you do not see them (look with db_query on the scratch table "
        "afterwards if you need to). Copying the same table again replaces the earlier copy. Tables that hold "
        "credentials are refused. A column of a type that exists only in the source (an enum) becomes text."
    )

    class Args(ToolArgs):
        table: str
        where: str = ""
        limit: int = Field(default=5000, ge=1, le=MAX_COPY_ROWS)
        source: Literal["local", "dev"] | None = None

    def summary(self, args: DbCopyTable.Args) -> str:
        return f"copy table {args.table}" + (f" where {args.where[:60]}" if args.where else "")

    async def run(self, args: DbCopyTable.Args, context: ToolContext) -> ToolResult:
        await _ensure_checked(context)
        db = context.db
        if db is None or db.scratch is None:
            return ToolResult(
                ok=False,
                content="No scratch schema is available, so nothing was copied. "
                + (db.status_line() if db else ""),
            )
        # The development database first: that is where the application's real data is.
        order = [args.source] if args.source else ["dev", *[name for name in db.targets if name != "dev"]]
        source = next((n for n in order if n in db.reports and db.reports[n].level != AccessLevel.NONE), None)
        if source is None:
            return ToolResult(ok=False, content="No reachable database to copy from. " + db.status_line())
        schema, _, table = args.table.strip().rpartition(".")
        try:
            result = await asyncio.to_thread(
                copy_table, db.scratch, db.targets[source], schema or "public", table, args.where, args.limit
            )
        except (SqlGuardError, ScratchError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        except psycopg.Error as error:
            return ToolResult(ok=False, content=f"Copy failed: {str(error).splitlines()[0]}")
        notes = []
        if result.capped:
            notes.append(
                f"More rows matched than the limit of {args.limit}; only the first {result.rows} were copied."
            )
        if result.as_text:
            notes.append(
                f"Stored as text (their type exists only in the source): {', '.join(result.as_text)}."
            )
        if result.numbered:
            notes.append(f"New rows continue the numbering of: {', '.join(result.numbered)}.")
        return ToolResult(
            ok=True,
            content=f"Copied {result.rows} row(s) of {source} {schema or 'public'}.{table} into the scratch table "
            f"{result.table} ({len(result.columns)} columns: {', '.join(result.columns[:30])}). "
            + " ".join(notes)
            + " Foreign keys, indexes and triggers are not copied.",
        )


class UseScratchDatabase(Tool):
    name = "use_scratch_database"
    description = (
        "Point the copy of the application at your scratch database, so that starting it here uses the tables "
        "you copied and never the real database. `variables` maps each setting the APPLICATION reads for its "
        "database (find them with code_map action env) to the part of the scratch connection it should get: "
        "`url`, `host`, `port`, `user`, `password`, `database` or `schema`; `url:<scheme>` gives the URL with "
        'another scheme (for example `url:postgresql+psycopg2` for SQLAlchemy). Example: {"DATABASE_URL": "url"} '
        'or {"DB_HOST": "host", "DB_PORT": "port", "DB_USER": "user", "DB_PASSWORD": "password", '
        '"DB_NAME": "database"}. From then on every command and background process you start has these set '
        "(and the search path set to the scratch schema); you never see the values. Start the application "
        "after this call, not before. An empty `variables` takes them out again."
    )

    class Args(ToolArgs):
        variables: dict[str, str]

    def summary(self, args: UseScratchDatabase.Args) -> str:
        return f"point the app at the scratch database: {', '.join(args.variables) or '(remove)'}"

    async def run(self, args: UseScratchDatabase.Args, context: ToolContext) -> ToolResult:
        db = context.db
        if db is None or db.scratch is None:
            return ToolResult(
                ok=False, content="No scratch schema is available. " + (db.status_line() if db else "")
            )
        try:
            db.set_app_variables(args.variables)
        except ValueError as error:
            return ToolResult(ok=False, content=str(error))
        if context.shell is not None:
            context.shell.extra_env = db.command_environment()
        if not args.variables:
            return ToolResult(
                ok=True, content="The application's database settings are no longer overridden."
            )
        return ToolResult(
            ok=True,
            content=f"Set for every command from now on: {', '.join(args.variables)} (values hidden), with the "
            f"search path on the scratch schema {db.scratch.schema}. A process that is already running keeps its "
            "old settings: stop it and start it again. If the application names a schema itself (public.table) "
            "or sets its own search path, it will not find the copied tables: check its database code.",
        )
