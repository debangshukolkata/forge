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

import psycopg
from pydantic import Field

from forge.db.access import AccessLevel
from forge.db.dev_write import (
    DevWriteError,
    WritePlan,
    apply_write,
    find_write,
    plan_write,
    record_write,
    undo_write,
)
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


def dev_db_tools() -> list[Tool]:
    return [DevDbWrite(), DevDbUndo()]
