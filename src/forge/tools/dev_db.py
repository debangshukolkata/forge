"""Changes to the shared development database, each one behind a red card (D-608): dev_db_write, dev_db_undo.

The user allows DebCraft to add and change rows in the development database when a requirement needs it, but the
database is on a server and everyone works in it. So the required step is in the tool, not in an instruction:
the statement is checked (one INSERT or UPDATE, nothing that deletes or changes a table), run and rolled back to
see what it does, shown to the user with the rows before and after, and committed only on their click. There is
no way to approve once for later calls.
"""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlsplit

import psycopg
from pydantic import Field

from forge.db.access import AccessLevel
from forge.db.dev_proxy import DevProxy, DevProxyError
from forge.db.dev_write import (
    DevWriteError,
    WritePlan,
    apply_write,
    find_write,
    plan_write,
    record_write,
    undo_write,
)
from forge.db.tunnel import TunnelError, ensure_tunnel
from forge.safety.sql_guard import SqlGuardError, check_dev_write
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.db import NO_DB, _ensure_checked

DEV = "dev"
SHOWN_ROWS = 5
SHOWN_COLUMNS = 8
SHOWN_VALUE = 80
NOTHING_CHANGED = "Nothing was changed in the development database."


def _value(value: object) -> str:
    """A value for the card: one line, short, and safe inside a markdown code span."""
    if value is None:
        return "NULL"
    text = " ".join(str(value).split()).replace("`", "'")
    return f"`{text[:SHOWN_VALUE]}{'…' if len(text) > SHOWN_VALUE else ''}`"


def _key_text(row: dict[str, Any], key: list[str]) -> str:
    return ", ".join(f"{column}={row.get(column)}" for column in key) or "(no primary key)"


def write_card(plan: WritePlan, reason: str) -> str:
    """What the user reads before approving: the statement, how many rows, and the first rows before and after."""
    count = len(plan.after)
    lines = [
        "**This changes the shared Development database.** Other people work in it.",
        "",
        f"Why DebCraft wants this: {reason.strip() or '(no reason given)'}",
        "",
        "```sql",
        plan.text,
        "```",
        "",
    ]
    if plan.kind == "update":
        lines.append(f"**{count} row(s) of `{plan.table}` will be changed:**")
        for index in range(min(count, SHOWN_ROWS)):
            changed = plan.changed(index)
            where = _key_text(plan.before[index], plan.key)
            if not changed:
                lines.append(f"- {where}: no value changes")
            for column in changed:
                old, new = plan.before[index].get(column), plan.after[index].get(column)
                lines.append(f"- {where}: **{column}** {_value(old)} → {_value(new)}")
        footer = "DebCraft keeps the old values in this project, so the update can be set back (after another card)."
    else:
        lines.append(f"**{count} row(s) will be added to `{plan.table}`:**")
        for row in plan.after[:SHOWN_ROWS]:
            filled = [(column, value) for column, value in row.items() if value is not None]
            shown = ", ".join(f"**{column}** {_value(value)}" for column, value in filled[:SHOWN_COLUMNS])
            more = f", and {len(filled) - SHOWN_COLUMNS} more columns" if len(filled) > SHOWN_COLUMNS else ""
            lines.append(f"- {shown}{more}")
        footer = (
            "Numbers that come from a sequence will be the next free ones. DebCraft never deletes in this "
            "database: taking these rows out again would be your step."
        )
    if count > SHOWN_ROWS:
        lines.append(f"- … and {count - SHOWN_ROWS} more row(s)")
    return "\n".join([*lines, "", footer])


async def _dev_target(context: ToolContext) -> tuple[Any, ToolResult | None]:
    """The development database of this session, or the reason there is none to write to."""
    await _ensure_checked(context)
    db = context.db
    if db is None:
        return None, NO_DB
    target = db.targets.get(DEV)
    if target is None or not target.url(db.secrets):
        return None, ToolResult(
            ok=False, content="No development database is configured (DEV_PG_URL in DebCraft's .env)."
        )
    report = db.reports.get(DEV)
    if report is None or report.level == AccessLevel.NONE:
        return None, ToolResult(
            ok=False, content="The development database is not reachable. " + db.status_line()
        )
    if context.confirm_danger is None:
        return None, ToolResult(
            ok=False,
            content="The user cannot be asked here, and a change to the development database needs their "
            f"approval each time. {NOTHING_CHANGED}",
        )
    return target, None


def _declined(note: str) -> ToolResult:
    said = f" The user said: {note}" if note else ""
    return ToolResult(
        ok=False,
        content=f"The user did not approve this change. {NOTHING_CHANGED}{said} Do not ask again for the same "
        "change; go on without it or ask the user what they want instead.",
    )


class DevDbWrite(Tool):
    name = "dev_db_write"
    description = (
        "Add or change rows in the shared DEVELOPMENT database, when a requirement cannot be solved on copied "
        "rows in your scratch schema (prefer db_copy_table and scratch_exec: they need no approval). `sql`: "
        "exactly one INSERT, or one UPDATE with a WHERE, on one table. DELETE, TRUNCATE, DROP, ALTER, CREATE and "
        "ON CONFLICT are refused: DebCraft never deletes or changes tables there. `reason`: one sentence for the "
        "user on why this row must change in the shared database. The user sees the statement and the rows "
        "before and after on a red card and approves each call; nothing is changed without that click, and at "
        "most 500 rows per call. The old values of an UPDATE are kept (dev_db_undo sets them back)."
    )

    class Args(ToolArgs):
        sql: str
        reason: str = Field(description="Why this change is needed in the shared database, for the user.")

    def summary(self, args: DevDbWrite.Args) -> str:
        return f"change the development database: {' '.join(args.sql.split())[:100]}"

    async def run(self, args: DevDbWrite.Args, context: ToolContext) -> ToolResult:
        target, problem = await _dev_target(context)
        if problem is not None or context.confirm_danger is None:
            return problem or NO_DB
        db = context.db
        try:
            write = check_dev_write(args.sql, db.deny_tables)
            plan = await asyncio.to_thread(plan_write, target, db.secrets, write)
        except (SqlGuardError, DevWriteError) as error:
            return ToolResult(ok=False, content=f"{error} {NOTHING_CHANGED}")
        except psycopg.Error as error:
            return ToolResult(
                ok=False, content=f"The statement failed: {str(error).splitlines()[0]} {NOTHING_CHANGED}"
            )
        verb = "Change" if plan.kind == "update" else "Add"
        count = len(plan.after)
        approved, note = await context.confirm_danger(
            f"{verb} {count} row(s) in the shared Development database ({plan.table})?",
            write_card(plan, args.reason),
            f"{verb} {count} row(s)",
        )
        if not approved:
            return _declined(note)
        try:
            done = await asyncio.to_thread(apply_write, target, db.secrets, plan)
        except DevWriteError as error:
            return ToolResult(ok=False, content=str(error))
        except psycopg.Error as error:
            return ToolResult(
                ok=False, content=f"The statement failed: {str(error).splitlines()[0]} {NOTHING_CHANGED}"
            )
        number = record_write(context.workspace, plan, done)
        did = "changed" if plan.kind == "update" else "added"
        await context.emit(
            "notice",
            {
                "kind": "dev_db_write",
                "text": f"Development database: {len(done)} row(s) {did} in {plan.table} (change {number}).",
            },
        )
        keys = "; ".join(_key_text(row, plan.key) for row in done[:20])
        after = (
            f"The old values are kept: dev_db_undo with write_id {number} sets them back."
            if plan.kind == "update"
            else "DebCraft does not delete rows there; if these must go again, tell the user which."
        )
        return ToolResult(
            ok=True,
            content=f"Approved by the user and committed: {len(done)} row(s) {did} in {plan.table} "
            f"(change {number}; rows: {keys}). {after}",
            meta={"dev_write": number},
        )


class DevDbUndo(Tool):
    name = "dev_db_undo"
    description = (
        "Set back an UPDATE that dev_db_write made in the development database in this project: `write_id` is "
        "the change number from its result. The user approves on a red card. Rows that someone else changed "
        "since are not overwritten (then nothing is set back). Rows added by an INSERT are not removed: "
        "DebCraft never deletes there."
    )

    class Args(ToolArgs):
        write_id: int = Field(ge=1)

    def summary(self, args: DevDbUndo.Args) -> str:
        return f"set back change {args.write_id} in the development database"

    async def run(self, args: DevDbUndo.Args, context: ToolContext) -> ToolResult:
        target, problem = await _dev_target(context)
        if problem is not None or context.confirm_danger is None:
            return problem or NO_DB
        record, undone = find_write(context.workspace, args.write_id)
        if record is None:
            return ToolResult(ok=False, content=f"There is no change {args.write_id} in this project's log.")
        if undone:
            return ToolResult(ok=False, content=f"Change {args.write_id} was already set back.")
        if record.get("kind") != "update":
            return ToolResult(
                ok=False,
                content=f"Change {args.write_id} added rows. DebCraft never deletes in the development "
                "database: tell the user which rows should go (their keys are in the result of that call).",
            )
        rows = [row for row in record["rows"] if row.get("old")]
        lines = [
            "**This changes the shared Development database.** It sets back an earlier change by DebCraft.",
            "",
            f"**{len(rows)} row(s) of `{record['table']}` get their old values back:**",
        ]
        for row in rows[:SHOWN_ROWS]:
            where = ", ".join(f"{column}={value}" for column, value in row["key"].items())
            for column, old in row["old"].items():
                lines.append(f"- {where}: **{column}** {_value(row['new'].get(column))} → {_value(old)}")
        if len(rows) > SHOWN_ROWS:
            lines.append(f"- … and {len(rows) - SHOWN_ROWS} more row(s)")
        approved, note = await context.confirm_danger(
            f"Set {len(rows)} row(s) back in the shared Development database ({record['table']})?",
            "\n".join(lines),
            f"Set {len(rows)} row(s) back",
        )
        if not approved:
            return _declined(note)
        try:
            restored = await asyncio.to_thread(
                undo_write, target, context.db.secrets, context.workspace, record
            )
        except DevWriteError as error:
            return ToolResult(ok=False, content=str(error))
        except psycopg.Error as error:
            return ToolResult(
                ok=False, content=f"Setting back failed: {str(error).splitlines()[0]} {NOTHING_CHANGED}"
            )
        await context.emit(
            "notice",
            {
                "kind": "dev_db_write",
                "text": f"Development database: change {args.write_id} set back ({restored} row(s) of "
                f"{record['table']}).",
            },
        )
        return ToolResult(
            ok=True, content=f"Set back: {restored} row(s) of {record['table']} have their old values again."
        )


RUN_CARD = (
    "**The copy of the application will read and write the shared Development database directly.** "
    "Other people work in it.\n\n"
    "Why DebCraft wants this: {reason}\n\n"
    "- Its settings {names} will point at the Development database, through DebCraft, until this session ends "
    "or DebCraft switches back.\n"
    "- **Rows it adds or changes there are real.** DebCraft lists them for you after each turn; it cannot show "
    "them before the application runs.\n"
    "- **Its DELETE, TRUNCATE and DROP statements are refused by DebCraft** and never reach the database. A "
    "delete hidden inside a database function or trigger is not seen.\n"
    "- The original repository is not touched: only the copy runs."
)


class UseDevDatabase(Tool):
    name = "use_dev_database"
    description = (
        "Run the copy of the application directly on the shared DEVELOPMENT database, when it needs more of the "
        "real data than is sensible to copy (prefer db_copy_table and use_scratch_database: they need no "
        "approval and nothing shared can change). `variables` maps each setting the APPLICATION reads for its "
        "database (find them with code_map action env) to the part of the connection it should get: `url`, "
        "`host`, `port`, `user`, `password` or `database`; `url:<scheme>` gives the URL with another scheme (for "
        'example `url:postgresql+psycopg2`). Example: {"DATABASE_URL": "url"}. `reason`: one sentence for the '
        "user. The user approves on a red card, once per session. From then on every command and background "
        "process you start has these set (you never see the values); the application connects through DebCraft, "
        "which refuses its DELETE, TRUNCATE and DROP statements and reports every row it adds or changes to the "
        "user. The address is local and without TLS: if the application forces TLS on its database connection, "
        "switch that off in the copy. Start the application after this call. An empty `variables` switches back "
        "to the scratch database. dev_db_activity shows what the application wrote."
    )

    class Args(ToolArgs):
        variables: dict[str, str]
        reason: str = Field(
            default="", description="Why the copied rows in the scratch schema are not enough."
        )

    def summary(self, args: UseDevDatabase.Args) -> str:
        return f"run the app on the development database: {', '.join(args.variables) or '(switch back)'}"

    async def run(self, args: UseDevDatabase.Args, context: ToolContext) -> ToolResult:
        db = context.db
        if not args.variables:
            if db is None or db.dev_proxy is None:
                return ToolResult(ok=True, content="The application was not on the development database.")
            report = db.dev_proxy.activity.summary(only_new=False)
            await db.dev_proxy.close()
            db.dev_proxy, db.dev_variables = None, {}
            if context.shell is not None:
                context.shell.extra_env = db.command_environment()
            return ToolResult(
                ok=True,
                content="Switched back: commands no longer get the development database. A process that is "
                "still running keeps its connection: stop it."
                + (f"\n\nIn this session:\n{report}" if report else ""),
            )
        target, problem = await _dev_target(context)
        if problem is not None or context.confirm_danger is None:
            return problem or NO_DB
        try:
            db.check_dev_variables(args.variables)
        except ValueError as error:
            return ToolResult(ok=False, content=str(error))
        if db.dev_proxy is None:  # one card per session; changing the names later needs no second one
            approved, note = await context.confirm_danger(
                "Run the copied application on the shared Development database?",
                RUN_CARD.format(
                    reason=args.reason.strip() or "(no reason given)",
                    names=", ".join(f"`{name}`" for name in args.variables),
                ),
                "Run it on the Development database",
            )
            if not approved:
                said = f" The user said: {note}" if note else ""
                return ToolResult(
                    ok=False,
                    content=f"The user did not approve this.{said} The application stays on the scratch "
                    "database: copy the rows it needs with db_copy_table. Do not ask again for the same thing.",
                )
            url = urlsplit(target.url(db.secrets) or "")
            proxy = DevProxy(url.hostname or "127.0.0.1", url.port or 5432, db.dev_sslmode())
            try:
                await asyncio.to_thread(ensure_tunnel, DEV)  # the tunnel the user described, if there is one
                await proxy.start()
            except (DevProxyError, TunnelError) as error:
                return ToolResult(ok=False, content=f"{error} The application was not switched over.")
            db.dev_proxy = proxy
        db.dev_variables = dict(args.variables)
        if context.shell is not None:
            context.shell.extra_env = db.command_environment()
        if context.pin is not None:
            context.pin("database", db.status_line())
        return ToolResult(
            ok=True,
            content=f"Approved by the user. Set for every command from now on: {', '.join(args.variables)} "
            "(values hidden), pointing at the development database through DebCraft. A process that is already "
            "running keeps its old settings: stop it and start it again. What the application writes there is "
            "real: keep it to what the requirement needs. Its DELETE, TRUNCATE and DROP statements fail with a "
            "database error that names DebCraft; that is the rule, not a bug to work around. The user is told "
            "after each turn what it wrote; dev_db_activity shows you the same."
            + (
                f" Still held back (they refuse a connection): {', '.join(db.still_held_back())}. Give them "
                "here too if the application connects with them."
                if db.still_held_back()
                else ""
            ),
        )


class DevDbActivity(Tool):
    name = "dev_db_activity"
    read_only = True
    description = (
        "What the copy of the application wrote to the development database in this session (after "
        "use_dev_database): its writing statements with how often each ran, the row counts the database "
        "reported, and the statements DebCraft refused (DELETE, TRUNCATE, DROP)."
    )

    class Args(ToolArgs):
        pass

    async def run(self, args: DevDbActivity.Args, context: ToolContext) -> ToolResult:
        db = context.db
        if db is None or db.dev_proxy is None:
            return ToolResult(
                ok=True, content="The application is not on the development database in this session."
            )
        report = db.dev_proxy.activity.summary(only_new=False)
        return ToolResult(
            ok=True,
            content=report or "The application has not written to the development database in this session.",
        )


def dev_db_tools() -> list[Tool]:
    return [DevDbWrite(), DevDbUndo(), UseDevDatabase(), DevDbActivity()]
