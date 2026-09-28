"""SQL guard (spec §9.5, §9.5.1): what Forge may run against a database.

- check_read_only: db_query on real schemas — SELECT/WITH/EXPLAIN/SHOW only, no writing keyword anywhere
  (catches data-modifying CTEs). The session also runs with default_transaction_read_only = on.
- check_scratch: scratch_exec — DDL/DML only inside the requirement's scratch schema; never other schemas,
  databases, roles, grants, DO blocks, COPY ... PROGRAM or file-reading functions.
- The credentials config table (deny-list) may never be referenced: its rows are secret.

A tokenizer that understands strings, dollar quotes, quoted identifiers and comments does the work, so a
keyword inside a string literal is never mistaken for a command.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from forge.errors import ForgeError

READ_START = {"select", "with", "explain", "show", "values", "table"}
WRITE_WORDS = {
    "insert",
    "update",
    "delete",
    "merge",
    "create",
    "alter",
    "drop",
    "truncate",
    "grant",
    "revoke",
    "copy",
    "call",
    "do",
    "vacuum",
    "reindex",
    "cluster",
    "comment",
    "refresh",
    "lock",
    "security",
    "reassign",
    "import",
    "listen",
    "notify",
    "prepare",
    "execute",
    "set",
}
FORBIDDEN_IN_SCRATCH = [
    (("drop", "database"), "dropping a database"),
    (("create", "database"), "creating a database"),
    (("create", "schema"), "creating schemas"),
    (("drop", "schema"), "dropping schemas"),
    (("alter", "schema"), "altering schemas"),
    (("alter", "role"), "changing roles"),
    (("alter", "user"), "changing users"),
    (("create", "role"), "creating roles"),
    (("create", "user"), "creating users"),
    (("drop", "role"), "dropping roles"),
    (("drop", "user"), "dropping users"),
    (("alter", "system"), "changing server settings"),
    (("set", "role"), "switching roles"),
    (("set", "session"), "changing session authorization"),
    (("set", "search_path"), "changing search_path (Forge sets it)"),
    (("reset", "role"), "switching roles"),
    (("create", "extension"), "installing extensions (ask the user via a DB request)"),
]
FORBIDDEN_WORDS = {
    "grant": "granting privileges",
    "revoke": "revoking privileges",
    "do": "anonymous code blocks",
    "security": "security labels",
}
FORBIDDEN_FUNCTIONS = {
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "lo_import",
    "lo_export",
    "dblink",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "set_config",
}
SYSTEM_SCHEMAS = {"pg_catalog", "information_schema"}
_CREATED = re.compile(
    r"^create\s+(?:or\s+replace\s+)?(?:unique\s+)?(?:temp\w*\s+|unlogged\s+)?"
    r"(table|view|materialized\s+view|sequence|function|procedure|index|type)\s+"
    r"(?:concurrently\s+)?(?:if\s+not\s+exists\s+)?([\w.\"]+)"
)


class SqlGuardError(ForgeError):
    """The statement is not allowed; the message says why (it is shown to the model)."""


@dataclass
class Statement:
    text: str  # original text
    words: list[str] = field(
        default_factory=list
    )  # lower-cased unquoted words and identifiers ("a.b" kept whole)
    functions: list[str] = field(default_factory=list)  # names followed by "("


def split_statements(sql: str) -> list[Statement]:
    statements: list[Statement] = []
    current: list[str] = []
    words: list[str] = []
    functions: list[str] = []
    index, length = 0, len(sql)

    def finish() -> None:
        text = "".join(current).strip()
        if text:
            statements.append(Statement(text, list(words), list(functions)))
        current.clear()
        words.clear()
        functions.clear()

    while index < length:
        char = sql[index]
        if sql.startswith("--", index):
            end = sql.find("\n", index)
            index = length if end == -1 else end
            continue
        if sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            index = length if end == -1 else end + 2
            continue
        if char == "'":
            end = index + 1
            while end < length:
                if sql[end] == "'" and sql.startswith("''", end):
                    end += 2
                    continue
                if sql[end] == "'":
                    break
                end += 1
            current.append(sql[index : end + 1])
            index = end + 1
            continue
        dollar = re.match(r"\$(\w*)\$", sql[index:])
        if dollar:
            tag = dollar.group(0)
            end = sql.find(tag, index + len(tag))
            end = length if end == -1 else end + len(tag)
            current.append(sql[index:end])
            index = end
            continue
        word = re.match(r'(?:"[^"]*"|[A-Za-z_][\w$]*)(?:\s*\.\s*(?:"[^"]*"|[A-Za-z_][\w$]*))*', sql[index:])
        if word:
            raw = word.group(0)
            normalised = ".".join(
                p.strip().strip('"') if p.strip().startswith('"') else p.strip().lower()
                for p in raw.split(".")
            )
            words.append(normalised)
            rest = sql[index + len(raw) :].lstrip()
            if rest.startswith("("):
                functions.append(normalised.split(".")[-1])
            current.append(raw)
            index += len(raw)
            continue
        if char == ";":
            finish()
            index += 1
            continue
        current.append(char)
        index += 1
    finish()
    return statements


def _references(statement: Statement, table: str) -> bool:
    table = table.lower()
    return any(word == table or word.endswith(f".{table}") for word in statement.words)


def check_read_only(sql: str, deny_tables: list[str]) -> list[Statement]:
    statements = split_statements(sql)
    if not statements:
        raise SqlGuardError("No SQL statement given.")
    for statement in statements:
        first = statement.words[0] if statement.words else ""
        if first not in READ_START:
            raise SqlGuardError(
                f"Only SELECT/WITH/EXPLAIN/SHOW are allowed on real schemas, not {first.upper()}."
            )
        writes = sorted(set(statement.words) & (WRITE_WORDS - {"set"}))
        if writes:
            raise SqlGuardError(f"Read-only queries can't contain {', '.join(w.upper() for w in writes)}.")
        _check_common(statement, deny_tables)
    return statements


def check_scratch(sql: str, scratch_schema: str, deny_tables: list[str]) -> list[Statement]:
    statements = split_statements(sql)
    if not statements:
        raise SqlGuardError("No SQL statement given.")
    scratch = scratch_schema.lower()
    for statement in statements:
        pairs = list(zip(statement.words, statement.words[1:], strict=False))
        for (first, second), reason in FORBIDDEN_IN_SCRATCH:
            if (first, second) in pairs:
                raise SqlGuardError(f"Not allowed in the scratch schema: {reason}.")
        if "copy" in statement.words and "program" in statement.words:
            raise SqlGuardError("Not allowed: COPY ... PROGRAM runs shell commands on the server.")
        for word, reason in FORBIDDEN_WORDS.items():
            if statement.words and statement.words[0] == word:
                raise SqlGuardError(f"Not allowed in the scratch schema: {reason}.")
        reading = bool(statement.words) and statement.words[0] in READ_START
        for qualified in [w for w in statement.words if "." in w]:
            schema = qualified.split(".")[0]
            if schema in SYSTEM_SCHEMAS and not reading:
                # The local role may be a superuser: catalog tables are for reading only.
                raise SqlGuardError(f"'{qualified}' is a system catalog: only SELECT may use it.")
            if schema not in (scratch, *SYSTEM_SCHEMAS) and not _is_column_reference(qualified, statement):
                raise SqlGuardError(
                    f"'{qualified}' is outside the scratch schema '{scratch_schema}'. Use unqualified names: "
                    "search_path points at the scratch schema."
                )
        _check_common(statement, deny_tables)
    return statements


def _is_column_reference(qualified: str, statement: Statement) -> bool:
    """alias.column (e.g. c.id) is not a schema reference: its first part is an alias or table
    in the query."""
    first = qualified.split(".")[0]
    names = {w.split(".")[-1] for w in statement.words}
    return first in names or (len(qualified.split(".")) == 2 and first in _aliases(statement))


def _aliases(statement: Statement) -> set[str]:
    aliases: set[str] = set()
    for index, word in enumerate(statement.words[:-1]):
        if word in ("from", "join", "update", "into") and index + 2 < len(statement.words):
            follower = statement.words[index + 2]
            if follower == "as" and index + 3 < len(statement.words):
                aliases.add(statement.words[index + 3])
            elif follower not in (
                "where",
                "on",
                "set",
                "values",
                "join",
                "left",
                "inner",
                "group",
                "order",
                "limit",
            ):
                aliases.add(follower)
    return aliases


def _check_common(statement: Statement, deny_tables: list[str]) -> None:
    for table in deny_tables:
        if _references(statement, table):
            raise SqlGuardError(f"'{table}' holds credentials: Forge never reads or changes its rows.")
    forbidden = sorted(set(statement.functions) & FORBIDDEN_FUNCTIONS)
    if forbidden:
        raise SqlGuardError(f"Not allowed: {', '.join(forbidden)}.")


def created_objects(statement: Statement) -> tuple[str, str] | None:
    """(kind, name) when the statement creates an object Forge must remember to drop later."""
    match = _CREATED.match(" ".join(statement.text.lower().split()))
    if match is None:
        return None
    return " ".join(match.group(1).split()), match.group(2).strip('"').split(".")[-1]
