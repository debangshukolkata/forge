"""The requirement's scratch schema (spec §9.5, A-4): where Forge may create and change things.

- One schema per requirement; the user creates it (DB request) unless Forge may create it itself.
- A registry in Forge home locks the schema to one workspace and records every object Forge creates, so
  cleanup (at the end or via `forge cleanup`) drops only Forge's own objects — never anything else.
- The app and tests reach it through PGOPTIONS search_path = scratch ONLY (no fall-through to public, A-5).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

from forge.config import Secrets
from forge.db.connection import DbTarget, connect, safe_schema_name
from forge.safety.sql_guard import check_scratch, created_objects
from forge.workspace.workspace import Workspace

MAX_ROWS = 200
DROP_ORDER = ["view", "materialized view", "function", "procedure", "index", "table", "sequence", "type"]


class ScratchError(Exception):
    pass


@dataclass
class ExecResult:
    rows: list[tuple[Any, ...]]
    columns: list[str]
    created: list[tuple[str, str]]
    status: list[str]


def scratch_name_for(workspace: Workspace) -> str:
    slug = "".join(c if c.isalnum() else "_" for c in workspace.info.name.lower()).strip("_")
    return safe_schema_name(f"forge_{slug}"[:48])


class ScratchRegistry:
    """<forge_home>/scratch_registry.json: which workspace owns which schema, and what Forge created in it."""

    def __init__(self, home: Path) -> None:
        self.path = home / "scratch_registry.json"

    def load(self) -> dict[str, Any]:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=1), encoding="utf-8")
        temporary.replace(self.path)

    def claim(self, key: str, workspace_root: str) -> None:
        data = self.load()
        entry = data.setdefault(key, {"workspace": workspace_root, "objects": []})
        owner = entry["workspace"]
        if owner and owner != workspace_root and Path(owner).exists():
            raise ScratchError(
                f"Scratch schema {key} is in use by workspace {entry['workspace']}. Use a separate "
                "schema per requirement, or clean that workspace up first (forge cleanup)."
            )
        entry["workspace"] = workspace_root
        self.save(data)

    def record(self, key: str, kind: str, name: str) -> None:
        data = self.load()
        objects = data.setdefault(key, {"workspace": "", "objects": []})["objects"]
        if [kind, name] not in objects:
            objects.append([kind, name])
        self.save(data)

    def objects(self, key: str) -> list[tuple[str, str]]:
        return [(kind, name) for kind, name in self.load().get(key, {}).get("objects", [])]

    def keep_only(self, key: str, objects: list[tuple[str, str]]) -> None:
        data = self.load()
        if key in data:
            data[key]["objects"] = [[kind, name] for kind, name in objects]
            self.save(data)

    def release(self, key: str) -> None:
        data = self.load()
        data.pop(key, None)
        self.save(data)


class ScratchSchema:
    def __init__(
        self,
        target: DbTarget,
        secrets: Secrets,
        schema: str,
        registry: ScratchRegistry,
        workspace: Workspace,
        deny_tables: list[str],
    ) -> None:
        self.target = target
        self.secrets = secrets
        self.schema = safe_schema_name(schema)
        self.registry = registry
        self.workspace = workspace
        self.deny_tables = deny_tables
        self.key = f"{target.name}:{self.schema}"

    def claim(self) -> None:
        self.registry.claim(self.key, str(self.workspace.root))

    def create_schema(self) -> None:
        """Only when Forge's role may and the user approved (scratch.create: forge_if_allowed)."""
        self.claim()
        with connect(self.target, self.secrets) as connection:
            connection.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.schema}"')
        self.registry.record(self.key, "schema", self.schema)

    def execute(self, sql: str) -> ExecResult:
        statements = check_scratch(sql, self.schema, self.deny_tables)
        self.claim()
        result = ExecResult(rows=[], columns=[], created=[], status=[])
        with connect(self.target, self.secrets, search_path=self.schema) as connection:
            for statement in statements:
                # Bytes: sent as-is (no parameter parsing); the guard above already vetted the text.
                cursor = connection.execute(statement.text.encode("utf-8"))
                result.status.append(cursor.statusmessage or "")
                if cursor.description:
                    result.columns = [c.name for c in cursor.description]
                    result.rows = cursor.fetchmany(MAX_ROWS)
                made = created_objects(statement)
                if made:
                    self.registry.record(self.key, made[0], made[1])
                    result.created.append(made)
        return result

    def clone_structure(self, source_schema: str, table: str) -> None:
        """Structure only — never rows — of a real table into the scratch schema (same database)."""
        source, name = safe_schema_name(source_schema), safe_schema_name(table)
        with connect(self.target, self.secrets) as connection:
            connection.execute(
                f'CREATE TABLE IF NOT EXISTS "{self.schema}"."{name}" (LIKE "{source}"."{name}" '
                f"INCLUDING ALL)"
            )
        self.registry.record(self.key, "table", name)

    def cleanup(self) -> list[str]:
        """Drops only the objects Forge recorded, never with CASCADE: dependants first (views, then objects
        in reverse creation order, so a referencing table goes before the one it references), repeated
        while that makes progress. Whatever can't be dropped stays in the registry for a later retry."""
        remaining = [
            obj for kind in DROP_ORDER for obj in reversed(self.registry.objects(self.key)) if obj[0] == kind
        ]
        forge_created_schema = ("schema", self.schema) in self.registry.objects(self.key)
        dropped: list[str] = []
        errors: dict[tuple[str, str], str] = {}
        with connect(self.target, self.secrets) as connection:
            progress = True
            while remaining and progress:
                progress = False
                for kind, name in list(remaining):
                    try:
                        connection.execute(
                            f'DROP {kind.upper()} IF EXISTS "{self.schema}"."{safe_schema_name(name)}"'
                        )
                    except psycopg.Error as error:
                        errors[(kind, name)] = str(error).splitlines()[0]
                        continue
                    remaining.remove((kind, name))
                    dropped.append(f"{kind} {name}")
                    progress = True
            dropped += [
                f"{kind} {name} (not dropped: {errors.get((kind, name), '')})" for kind, name in remaining
            ]
            if forge_created_schema:
                try:  # never CASCADE: objects someone else put there keep the schema alive
                    connection.execute(f'DROP SCHEMA IF EXISTS "{self.schema}"')
                    dropped.append(f"schema {self.schema}")
                    forge_created_schema = False
                except psycopg.Error:
                    dropped.append(f"schema {self.schema} (kept: it still holds objects)")
        kept = [*remaining, *([("schema", self.schema)] if forge_created_schema else [])]
        if kept:
            self.registry.keep_only(self.key, kept)
        else:
            self.registry.release(self.key)
        return dropped


def pgoptions(schema: str) -> str:
    """For every command Forge runs: libpq applies this to all the app's connections (A-5: scratch only)."""
    return f"-c search_path={safe_schema_name(schema)}"
