"""Before DB-backed test runs (spec §9.5, "every table the code touches must exist in scratch"):

- tables the app code uses (SQLAlchemy models + raw SQL, read fresh from the workspace copy, tests excluded)
  that don't exist in the scratch schema are reported, so a "relation does not exist" failure is explained
  before it happens and the agent creates them (clone structure / DDL) or files a DB request;
- raw SQL that WRITES to a schema-qualified table (`public.claims`) bypasses the scratch search_path; against
  a remote database such a run is refused (R28), because it would write to the shared tables.

Missing tables are reported, not refused (DECISIONS D-107): many suites use SQLite fixtures and never touch
the scratch schema, so refusing would block runs that are safe.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge.kb.data_facts import extract_models, extract_sql_usage
from forge.kb.python_index import parse_module
from forge.workspace.copy_repo import iter_source_files
from forge.workspace.workspace import Workspace

WRITE_OPERATIONS = {"INSERT", "UPDATE", "DELETE", "MERGE", "TRUNCATE", "CREATE", "ALTER", "DROP"}
LOCAL_TARGET = "local"

_cache: dict[tuple[str, tuple[tuple[str, float], ...]], CodeTables] = {}


@dataclass
class CodeTables:
    tables: set[str] = field(default_factory=set)
    qualified_writes: list[str] = field(default_factory=list)  # "path:line — snippet"


@dataclass
class TableCheck:
    missing: list[str]
    refusal: str | None = None

    def note(self, schema: str) -> str:
        if self.refusal:
            return self.refusal
        if not self.missing:
            return ""
        return (
            f"[Forge: tables the code uses are missing from the scratch schema {schema}: "
            f"{', '.join(self.missing)}. Tests that use the database will fail with 'relation does not "
            "exist'. Create them there first (clone the structure of the real table, or run the DDL with "
            "scratch_exec), or file a db_request if Forge can't.]"
        )


def code_tables(workspace: Workspace) -> CodeTables:
    """Tables the app's non-test code touches, from the current workspace copy (cached by file mtimes)."""
    repo, app = workspace.repo_dir, workspace.info.app_subfolder
    rules = workspace.ignore_rules()
    files = [
        (relative, Path(source))
        for relative, source, is_link in iter_source_files(repo, app, rules)
        if relative.endswith(".py") and not is_link and not rules.is_secret(relative)
    ]
    key = (str(repo), tuple(sorted((r, p.stat().st_mtime) for r, p in files)))
    if key in _cache:
        return _cache[key]
    modules = [m for relative, _ in files if (m := parse_module(repo, relative, app)) is not None]
    usage, _ = extract_sql_usage(modules)
    result = CodeTables(
        tables={m.table.split(".")[-1].lower() for m in extract_models(modules)}
        | {t.lower() for u in usage if not u.in_tests for t in u.tables},
        qualified_writes=[
            f"{u.path}:{u.line} — {u.snippet[:100]}"
            for u in usage
            if u.schema_qualified and not u.in_tests and u.operation in WRITE_OPERATIONS
        ],
    )
    _cache.clear()  # one workspace per session: keep only the latest
    _cache[key] = result
    return result


def scratch_tables(db: Any) -> set[str]:
    """Blocking: the tables (and views) that exist in the scratch schema."""
    from forge.db.connection import connect

    scratch = db.scratch
    with connect(scratch.target, scratch.secrets) as connection:
        rows = connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s", (scratch.schema,)
        ).fetchall()
    return {str(row[0]).lower() for row in rows}


def check_tables(workspace: Workspace, db: Any) -> TableCheck | None:
    """None when no scratch schema is in use (tests then can't reach a real database through Forge)."""
    if db is None or db.scratch is None:
        return None
    code = code_tables(workspace)
    if code.qualified_writes and db.scratch.target.name != LOCAL_TARGET:
        return TableCheck(
            missing=[],
            refusal=(
                "Not run: this code writes to schema-qualified tables, which bypass the scratch schema, and "
                f"the scratch schema is on the shared '{db.scratch.target.name}' database — the run would "
                "write to real tables there:\n"
                + "\n".join(f"- {w}" for w in code.qualified_writes[:10])
                + "\nUse unqualified table names (the app's search_path decides the schema), run against the "
                "local database, or ask the user."
            ),
        )
    existing = scratch_tables(db)
    return TableCheck(missing=sorted(code.tables - existing - set(db.deny_tables)))
