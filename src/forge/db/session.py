"""The workspace's database situation (spec §9.5.2): access level per database, the chosen target, the
requirement's scratch schema, DB requests — and the environment every command gets so the app and tests
use the scratch schema only (A-5)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import psycopg

from forge.config import PostgresConfig, Secrets
from forge.db.access import AccessLevel, AccessReport, detect
from forge.db.connection import DbTarget, connect
from forge.db.requests import DbRequest, DbRequests
from forge.db.scratch import ScratchRegistry, ScratchSchema, pgoptions, scratch_name_for
from forge.safety.sql_guard import SqlGuardError, check_read_only
from forge.workspace.workspace import Workspace

APP_ENV_FILE = "db_app_env.json"  # in the workspace's .forge folder: setting names only, never a value
APP_VARIABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,80}$")
CONNECTION_PARTS = ("url", "host", "port", "user", "password", "database", "schema")


class DbSession:
    def __init__(
        self,
        config: PostgresConfig,
        secrets: Secrets,
        workspace: Workspace,
        home: Path,
        deny_tables: list[str],
    ) -> None:
        self.config = config
        self.secrets = secrets
        self.workspace = workspace
        self.home = home
        self.deny_tables = sorted({t.lower() for t in [*config.deny_tables, *deny_tables]})
        self.targets = {
            name: DbTarget(name, c.url_env, c.sslmode, c.statement_timeout_s, c.lock_timeout_s)
            for name, c in config.connections.items()
        }
        self.reports: dict[str, AccessReport] = {}
        self.scratch: ScratchSchema | None = None
        self.requests = DbRequests(workspace)

    def add_deny_tables(self, tables: list[str]) -> None:
        self.deny_tables = sorted({*self.deny_tables, *(t.lower() for t in tables)})
        if self.scratch is not None:
            self.scratch.deny_tables = self.deny_tables

    @property
    def scratch_schema_name(self) -> str:
        return scratch_name_for(self.workspace)

    def detect(self) -> dict[str, AccessReport]:
        """Blocking (use asyncio.to_thread): tries every configured database that has a URL."""
        self.reports = {
            name: detect(target, self.secrets, self.scratch_schema_name)
            for name, target in self.targets.items()
            if target.url(self.secrets)
        }
        return self.reports

    def preferred_target(self) -> str | None:
        """Where the scratch schema lives: the preferred database if DebCraft can write there, else the other."""
        order = [self.config.prefer, *[n for n in self.targets if n != self.config.prefer]]
        writable = [n for n in order if n in self.reports and self.reports[n].level == AccessLevel.WRITE]
        return writable[0] if writable else None

    def activate_scratch(self, target_name: str) -> ScratchSchema:
        scratch = ScratchSchema(
            self.targets[target_name],
            self.secrets,
            self.scratch_schema_name,
            ScratchRegistry(self.home),
            self.workspace,
            self.deny_tables,
        )
        scratch.claim()
        self.scratch = scratch
        return scratch

    def command_environment(self) -> dict[str, str]:
        """Added to every command DebCraft runs once the scratch schema is ready: the search path, and the
        application's own database settings pointed at the scratch database when the model asked for that."""
        if self.scratch is None:
            return {}
        return {"PGOPTIONS": pgoptions(self.scratch.schema), **self._app_values()}

    # --- the application copy pointed at the scratch database (D-568) ---

    def app_variables(self) -> dict[str, str]:
        """The application's setting names and which part of the scratch connection each gets (names only)."""
        try:
            data = json.loads((self.workspace.forge_dir / APP_ENV_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {str(name): str(part) for name, part in data.items()} if isinstance(data, dict) else {}

    def set_app_variables(self, variables: dict[str, str]) -> None:
        for name, part in variables.items():
            if not APP_VARIABLE.match(name):
                raise ValueError(f"{name!r} is not a plain environment variable name.")
            if part.partition(":")[0] not in CONNECTION_PARTS:
                raise ValueError(f"{part!r} is not one of {', '.join(CONNECTION_PARTS)} (or url:<scheme>).")
        target = self.workspace.jail.check(self.workspace.forge_dir / APP_ENV_FILE)
        target.write_text(json.dumps(variables, indent=1), encoding="utf-8")

    def _app_values(self) -> dict[str, str]:
        variables = self.app_variables()
        url = self.scratch.target.url(self.secrets) if self.scratch and variables else None
        if not url or self.scratch is None:
            return {}
        parsed = urlsplit(url)
        parts = {
            "url": url,
            "host": parsed.hostname or "",
            "port": str(parsed.port or 5432),
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "database": parsed.path.lstrip("/"),
            "schema": self.scratch.schema,
        }
        values: dict[str, str] = {}
        for name, part in variables.items():
            kind, _, scheme = part.partition(":")
            values[name] = url.replace(parsed.scheme, scheme, 1) if kind == "url" and scheme else parts[kind]
        return values

    def status_line(self) -> str:
        if not self.reports:
            return "Databases: not checked yet."
        lines = [report.line() for report in self.reports.values()]
        lines.append(
            f"Scratch schema in use: {self.scratch.target.name} / {self.scratch.schema}"
            + self._scratch_contents()
            if self.scratch
            else "No scratch schema in use: DebCraft can't run SQL or DB-backed tests here. For every new SQL "
            "script, call db_request (exact SQL + verification query; the user or their DBA runs it), and "
            "mark_server_run any test that needs the database. Never present such SQL as checked."
        )
        pending = [r.id for r in self.requests.all() if r.status == "pending"]
        if pending:
            lines.append(f"Pending DB requests: {', '.join(pending)}")
        return "\n".join(lines)

    def _scratch_contents(self) -> str:
        """What an earlier session already put there: the tables copied or created, and the settings of the
        application that point at it (they are applied again at every session start, D-597)."""
        if self.scratch is None:
            return ""
        tables = [name for kind, name in self.scratch.registry.objects(self.scratch.key) if kind == "table"]
        parts = []
        if tables:
            shown = ", ".join(tables[:25]) + (f" and {len(tables) - 25} more" if len(tables) > 25 else "")
            parts.append(f"tables already in it (copied or created earlier, kept between sessions): {shown}")
        variables = self.app_variables()
        if variables:
            parts.append(
                f"the application's settings {', '.join(variables)} already point at it (applied automatically at "
                "session start; no need to call use_scratch_database again unless the application changed)"
            )
        return (". " + "; ".join(parts)) if parts else ""

    def create_request(
        self, title: str, purpose: str, sql: str, verification_query: str, who: str = "you"
    ) -> DbRequest:
        target = self.preferred_target() or self.config.prefer
        where = f"{target} database, schema {self.scratch_schema_name}"
        return self.requests.create(
            title,
            purpose,
            where,
            sql,
            verification_query,
            "your DBA" if who.lower().startswith("dba") or "dba" in who.lower() else "you",
        )

    def verify_request(self, request: DbRequest, pasted: str | None) -> tuple[bool, str]:
        """At L2/L3 DebCraft runs the verification query itself; at L1 it relies on the pasted result."""
        reachable = [n for n, r in self.reports.items() if r.level != AccessLevel.NONE]
        if not reachable:
            if pasted and pasted.strip():
                return True, "Verified from the result you pasted."
            return (
                False,
                "DebCraft can't reach the database: paste the verification query's result (no data rows).",
            )
        try:
            check_read_only(request.verification_query, self.deny_tables)
        except SqlGuardError as error:
            return False, f"The verification query isn't read-only: {error}"
        target = self.targets[reachable[0]]
        try:
            with connect(
                target,
                self.secrets,
                read_only=True,
                search_path=self.scratch_schema_name if self.scratch else None,
            ) as connection:
                rows = connection.execute(request.verification_query.encode("utf-8")).fetchmany(20)
        except psycopg.Error as error:
            return False, f"The verification query failed: {str(error).splitlines()[0]}"
        return (
            (True, f"Verified: {len(rows)} row(s).")
            if rows
            else (False, "The verification query returned no rows.")
        )
