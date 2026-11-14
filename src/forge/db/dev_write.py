"""One approved INSERT or UPDATE on the shared development database (D-608).

The user allows DebCraft to add and change rows there, each time after they have seen what will change on a red
card, and never to delete. So a write happens in three steps: `plan_write` runs the statement and rolls it back,
which gives the rows it would leave and, for an UPDATE, the rows as they are now; the tool shows that to the user;
`apply_write` runs it again and commits only if the rows are still as the card showed them. The old values of an
UPDATE are kept in the project's `.forge` folder so `undo_write` can set them back. An INSERT is not taken out
again by DebCraft: that would be a delete.

Values are read as text (`column::text`), so a row can be written to the log and set back whatever its types are.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

from forge.config import Secrets
from forge.db.connection import DbTarget, connect
from forge.db.copy_rows import PRIMARY_KEY_SQL
from forge.errors import ForgeError
from forge.safety.sql_guard import DevWrite
from forge.workspace.workspace import Workspace

MAX_ROWS = 500  # a statement that touches more is not sent to a database other people work in
LOG_FILE = "dev_writes.jsonl"
COLUMNS_SQL = """
SELECT attname, format_type(atttypid, atttypmod) FROM pg_attribute
WHERE attrelid = %s::regclass AND attnum > 0 AND NOT attisdropped AND attgenerated = ''
ORDER BY attnum
"""

Row = dict[str, str | None]
Key = tuple[str | None, ...]


class DevWriteError(ForgeError):
    """The change was not made; the message says why (it is shown to the model)."""


@dataclass
class WritePlan:
    kind: str  # "insert" or "update"
    table: str
    text: str
    columns: list[str]
    key: list[str]
    after: list[Row]  # the rows as the statement leaves them
    before: list[Row] = field(default_factory=list)  # UPDATE: the same rows as they are now, same order
    # The statement named the table without its schema and it is not in the default one: the schema it was
    # found in. The statement then runs with the search path on that schema.
    search_path: str = ""

    def changed(self, index: int) -> list[str]:
        """The columns of row `index` whose value the UPDATE changes."""
        return [c for c in self.columns if self.before[index].get(c) != self.after[index].get(c)]


def _identifier(table: str) -> sql.Identifier:
    return sql.Identifier(*table.split("."))


def _shape(connection: psycopg.Connection[Any], table: str) -> tuple[dict[str, str], list[str]]:
    """Column name -> type as PostgreSQL writes it, and the primary key columns."""
    qualified = _identifier(table).as_string(None)
    found = connection.execute("SELECT to_regclass(%s)", (qualified,)).fetchone()
    if found is None or found[0] is None:
        raise DevWriteError(f"The table {table} was not found in the development database.")
    types = {name: kind for name, kind in connection.execute(COLUMNS_SQL, (qualified,)).fetchall()}
    key = [row[0] for row in connection.execute(PRIMARY_KEY_SQL, (qualified,)).fetchall()]
    return types, key


SCHEMAS_SQL = """
SELECT schemaname FROM pg_tables
WHERE tablename = %s AND schemaname NOT IN ('pg_catalog', 'information_schema') ORDER BY schemaname
"""


def _locate(connection: psycopg.Connection[Any], table: str) -> tuple[str, str]:
    """The table as `schema.table` and, when the statement did not name the schema and the table is not in the
    default one, the schema to put on the search path. In a live run the model wrote `UPDATE agents ...` for a
    table that lives in the application's own schema, was told "not found" and handed the change to the user;
    which schema holds the table is something the tool can look up."""
    if "." in table:
        return table, ""
    found = connection.execute("SELECT to_regclass(%s)", (_identifier(table).as_string(None),)).fetchone()
    if found is not None and found[0] is not None:
        return table, ""
    schemas = [row[0] for row in connection.execute(SCHEMAS_SQL, (table,)).fetchall()]
    if len(schemas) == 1:
        return f"{schemas[0]}.{table}", schemas[0]
    if not schemas:
        raise DevWriteError(
            f"There is no table {table} in the development database. db_schema shows its schemas and tables."
        )
    shown = ", ".join(f"{schema}.{table}" for schema in schemas[:10])
    raise DevWriteError(
        f"The table {table} exists in {len(schemas)} schemas: {shown}. Write it with its schema in the statement "
        "(the one the application uses: its schema setting, see code_map action env) and call again."
    )


def _use_schema(connection: psycopg.Connection[Any], schema: str) -> None:
    """Inside a transaction: unqualified names of the statement are looked up in this schema until it ends."""
    if schema:
        connection.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))


def _as_text(columns: list[str]) -> sql.Composable:
    return sql.SQL(", ").join(sql.SQL("{}::text").format(sql.Identifier(column)) for column in columns)


def _run(connection: psycopg.Connection[Any], write_text: str, columns: list[str]) -> list[Row]:
    """Runs the statement and returns the rows it leaves, as text. The statement is the model's text, checked by
    `check_dev_write`; it carries no parameters, so a percent sign in it is not a placeholder."""
    statement = sql.SQL("{} RETURNING {}").format(sql.SQL(write_text), _as_text(columns))
    try:
        rows = connection.execute(statement).fetchmany(MAX_ROWS + 1)
    except psycopg.errors.AmbiguousColumn as error:
        raise DevWriteError(
            "Write the UPDATE without FROM (put the other table into a subquery in WHERE or SET): with a second "
            "table the changed rows cannot be read back."
        ) from error
    if len(rows) > MAX_ROWS:
        raise DevWriteError(
            f"The statement touches more than {MAX_ROWS} rows. Narrow it: the development database is shared."
        )
    return [dict(zip(columns, row, strict=True)) for row in rows]


def _key_of(row: Row, key: list[str]) -> Key:
    return tuple(row.get(column) for column in key)


def _rows_by_key(
    connection: psycopg.Connection[Any],
    table: str,
    columns: list[str],
    key: list[str],
    keys: list[Key],
    lock: bool = False,
) -> dict[Key, Row]:
    if not keys:
        return {}
    one = sql.SQL("(") + sql.SQL(", ").join(sql.Placeholder() * len(key)) + sql.SQL(")")
    query = sql.SQL("SELECT {} FROM {} WHERE ({}) IN ({}){}").format(
        _as_text(columns),
        _identifier(table),
        _as_text(key),
        sql.SQL(", ").join(one for _ in keys),
        sql.SQL(" FOR UPDATE") if lock else sql.SQL(""),
    )
    values = [part for item in keys for part in item]
    rows = [dict(zip(columns, row, strict=True)) for row in connection.execute(query, values).fetchall()]
    return {_key_of(row, key): row for row in rows}


def plan_write(target: DbTarget, secrets: Secrets, write: DevWrite) -> WritePlan:
    """What the statement would do, without doing it: it runs inside a transaction that is rolled back."""
    with connect(target, secrets) as connection:
        table, schema = _locate(connection, write.table)
        types, key = _shape(connection, table)
        columns = list(types)
        if write.kind == "update" and not key:
            raise DevWriteError(
                f"{table} has no primary key, so the old values could not be set back. DebCraft does not "
                "update such a table in the development database; tell the user what should change."
            )
        with connection.transaction(force_rollback=True):
            _use_schema(connection, schema)
            after = _run(connection, write.text, columns)
        if not after:
            raise DevWriteError("The statement matches no rows, so there is nothing to change.")
        plan = WritePlan(write.kind, table, write.text, columns, key, after, search_path=schema)
        if write.kind == "update":
            now = _rows_by_key(connection, table, columns, key, [_key_of(row, key) for row in after])
            if len(now) != len(after):
                raise DevWriteError(
                    "The statement changes the primary key of a row; such a change could not be set back and is "
                    "not sent to the development database."
                )
            plan.before = [now[_key_of(row, key)] for row in after]
    return plan


def apply_write(target: DbTarget, secrets: Secrets, plan: WritePlan) -> list[Row]:
    """Runs the approved statement and commits it, if the rows are still what the user saw on the card."""
    with connect(target, secrets) as connection, connection.transaction():
        if plan.kind == "update":
            keys = [_key_of(row, plan.key) for row in plan.before]
            locked = _rows_by_key(connection, plan.table, plan.columns, plan.key, keys, lock=True)
            if [locked.get(item) for item in keys] != plan.before:
                raise DevWriteError(
                    "The rows changed in the development database after the card was shown, so nothing was "
                    "changed. Call the tool again: the user is asked again with the rows as they are now."
                )
        _use_schema(connection, plan.search_path)
        done = _run(connection, plan.text, plan.columns)
        same = (
            sorted(map(str, (_key_of(row, plan.key) for row in done)))
            == sorted(map(str, (_key_of(row, plan.key) for row in plan.after)))
            if plan.kind == "update"
            else len(done) == len(plan.after)
        )
        if not same:  # leaving the block with an error rolls the transaction back
            raise DevWriteError(
                "The statement now touches other rows than the card showed, so nothing was changed. Call the "
                "tool again."
            )
    return done


# --- the log in the project's .forge folder: what was changed, and the old values of an UPDATE ---


def _log_path(workspace: Workspace) -> Path:
    return workspace.jail.check(workspace.forge_dir / LOG_FILE)


def read_log(workspace: Workspace) -> list[dict[str, Any]]:
    try:
        lines = _log_path(workspace).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    records = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except ValueError:
            continue
    return records


def _append(workspace: Workspace, record: dict[str, Any]) -> None:
    path = _log_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    earlier = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(earlier + json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")


def record_write(workspace: Workspace, plan: WritePlan, done: list[Row]) -> int:
    """Writes the change to the log and returns its number. For an UPDATE each row keeps the old and the new
    value of the columns that changed; for an INSERT only the key of each new row."""
    number = 1 + sum(1 for record in read_log(workspace) if "id" in record)
    rows: list[dict[str, Any]] = []
    if plan.kind == "update":
        by_key = {_key_of(row, plan.key): row for row in done}
        for before in plan.before:
            new = by_key[_key_of(before, plan.key)]
            changed = [c for c in plan.columns if before.get(c) != new.get(c)]
            rows.append(
                {
                    "key": {c: before.get(c) for c in plan.key},
                    "old": {c: before.get(c) for c in changed},
                    "new": {c: new.get(c) for c in changed},
                }
            )
    else:
        rows = [{"key": {c: row.get(c) for c in plan.key}} for row in done]
    _append(
        workspace,
        {
            "id": number,
            "time": datetime.now().isoformat(timespec="seconds"),
            "kind": plan.kind,
            "table": plan.table,
            "statement": plan.text,
            "rows": rows,
        },
    )
    return number


def find_write(workspace: Workspace, number: int) -> tuple[dict[str, Any] | None, bool]:
    """The logged change with that number, and whether it was already set back."""
    records = read_log(workspace)
    found = next((record for record in records if record.get("id") == number), None)
    return found, any(record.get("undo_of") == number for record in records)


def undo_write(target: DbTarget, secrets: Secrets, workspace: Workspace, record: dict[str, Any]) -> int:
    """Sets the old values of a logged UPDATE back, row by row, in one transaction. A row that someone changed
    since (its values are no longer the ones DebCraft wrote) stops the whole undo: nothing is overwritten."""
    table = str(record["table"])
    restored = 0
    with connect(target, secrets) as connection, connection.transaction():
        types, _ = _shape(connection, table)
        for row in record["rows"]:
            key = list(row["key"])
            changed = [column for column in row["old"] if column in types]
            if not changed:
                continue
            item: Key = tuple(row["key"][column] for column in key)
            current = _rows_by_key(connection, table, changed, key, [item], lock=True)
            where = ", ".join(f"{column}={value}" for column, value in row["key"].items())
            # _rows_by_key keys its result by the selected columns' key values; here the selection is the changed
            # columns only, so take the single row it found.
            found = next(iter(current.values()), None) if current else None
            if found is None:
                raise DevWriteError(f"The row {where} of {table} no longer exists; nothing was set back.")
            if any(found.get(column) != row["new"].get(column) for column in changed):
                raise DevWriteError(
                    f"The row {where} of {table} was changed by someone after DebCraft's update; nothing was "
                    "set back, so their change is not overwritten."
                )
            assignments = sql.SQL(", ").join(
                # the type comes from the catalog (format_type), not from the model or the log
                sql.SQL("{} = (%s::text)::{}").format(sql.Identifier(column), sql.SQL(types[column]))
                for column in changed
            )
            condition = sql.SQL(" AND ").join(
                sql.SQL("{}::text = %s").format(sql.Identifier(column)) for column in key
            )
            statement = sql.SQL("UPDATE {} SET {} WHERE {}").format(
                _identifier(table), assignments, condition
            )
            connection.execute(statement, [*(row["old"][column] for column in changed), *item])
            restored += 1
    _append(
        workspace,
        {"undo_of": record["id"], "time": datetime.now().isoformat(timespec="seconds"), "rows": restored},
    )
    return restored
