"""The workspace's database situation (spec §9.5.2): access level per database, the chosen target, the
requirement's scratch schema, DB requests — and the environment every command gets so the app and tests
use the scratch schema only (A-5)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

import psycopg

from forge.config import PostgresConfig, Secrets
from forge.db.access import AccessLevel, AccessReport, detect
from forge.db.connection import DbTarget, connect
from forge.db.dev_guard import HeldBack, Refuser, dev_settings
from forge.db.dev_proxy import DevProxy
from forge.db.requests import DbRequest, DbRequests
from forge.db.scratch import ScratchRegistry, ScratchSchema, pgoptions, scratch_name_for
from forge.safety.sql_guard import SqlGuardError, check_read_only
from forge.workspace.workspace import Workspace

APP_ENV_FILE = "db_app_env.json"  # in the workspace's .forge folder: setting names only, never a value
APP_VARIABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,80}$")
CONNECTION_PARTS = ("url", "host", "port", "user", "password", "database", "schema")
DEV_CONNECTION_PARTS = ("url", "host", "port", "user", "password", "database")


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
        # The copied application on the development database (D-610): the relay it connects to and the names of
        # its settings. Only for this session, never written to disk: the next session asks the user again.
        self.dev_proxy: DevProxy | None = None
        self.dev_variables: dict[str, str] = {}
        # The copy's own settings that point at the development database (D-613): held back until the model
        # points the application somewhere on purpose. `dev_refuser` answers connections made with them.
        self.dev_held: HeldBack = HeldBack()
        self.dev_refuser: Refuser | None = None

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

    @property
    def on_dev_database(self) -> bool:
        """The application's settings point at the development database in this session. Read with getattr:
        some callers build a session without its constructor."""
        return getattr(self, "dev_proxy", None) is not None and bool(getattr(self, "dev_variables", None))

    def command_environment(self) -> dict[str, str]:
        """Added to every command DebCraft runs once the scratch schema is ready: the search path, and the
        application's own database settings pointed at the scratch database when the model asked for that."""
        held = self.held_back_values()
        if self.on_dev_database:
            # No search path here: the application must see the development database's own schemas.
            return {**held, **self.dev_app_values()}
        if self.scratch is None:
            return held
        return {**held, "PGOPTIONS": pgoptions(self.scratch.schema), **self._app_values()}

    # --- the copy's own settings that point at the development database (D-613) ---

    def find_dev_settings(self) -> HeldBack:
        """Blocking (reads the copy's env files): which of its settings hold the development database's address."""
        url = self.targets["dev"].url(self.secrets) if "dev" in self.targets else None
        if not url:
            return HeldBack()
        return dev_settings([self.workspace.repo_dir, self.workspace.app_dir], url)

    def held_back_values(self) -> dict[str, str]:
        refuser = getattr(self, "dev_refuser", None)
        held = getattr(self, "dev_held", None)
        return held.values(refuser.local_port) if refuser is not None and held is not None else {}

    def still_held_back(self) -> list[str]:
        """The held-back settings that neither use_scratch_database nor use_dev_database has replaced."""
        if getattr(self, "dev_refuser", None) is None:
            return []
        replaced = set(self.dev_variables) if self.on_dev_database else set(self.app_variables())
        return [name for name in self.dev_held.kinds if name not in replaced]

    # --- the application copy on the development database, through DebCraft's relay (D-610) ---

    def dev_sslmode(self) -> str:
        url = self.targets["dev"].url(self.secrets) or ""
        return dict(parse_qsl(urlsplit(url).query)).get("sslmode") or self.targets["dev"].sslmode

    def check_dev_variables(self, variables: dict[str, str]) -> None:
        for name, part in variables.items():
            if not APP_VARIABLE.match(name):
                raise ValueError(f"{name!r} is not a plain environment variable name.")
            if part.partition(":")[0] not in DEV_CONNECTION_PARTS:
                raise ValueError(
                    f"{part!r} is not one of {', '.join(DEV_CONNECTION_PARTS)} (or url:<scheme>)."
                )

    def dev_app_values(self) -> dict[str, str]:
        """The application's database settings for the development database: its own user, password and
        database name, but the address of the relay on this machine instead of the server's."""
        url = self.targets["dev"].url(self.secrets) if "dev" in self.targets else None
        if not url or self.dev_proxy is None:
            return {}
        parsed = urlsplit(url)
        login = parsed.netloc.rpartition("@")[0]
        # The relay speaks plain PostgreSQL on localhost and does the TLS to the server itself.
        query = urlencode(
            [(k, v) for k, v in parse_qsl(parsed.query) if k != "sslmode"] + [("sslmode", "disable")]
        )
        port = str(self.dev_proxy.local_port)
        local = urlunsplit(
            parsed._replace(netloc=f"{login + '@' if login else ''}127.0.0.1:{port}", query=query)
        )
        parts = {
            "url": local,
            "host": "127.0.0.1",
            "port": port,
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "database": parsed.path.lstrip("/"),
        }
        values: dict[str, str] = {}
        for name, part in self.dev_variables.items():
            kind, _, scheme = part.partition(":")
            values[name] = (
                local.replace(parsed.scheme, scheme, 1) if kind == "url" and scheme else parts[kind]
            )
        return values

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
        held = self.still_held_back()
        if held:
            lines.append(
                f"HELD BACK: the copy's own settings {', '.join(held)} (in {', '.join(self.dev_held.files)}) point "
                "at the shared development database. Commands get an address that refuses the connection for "
                "them. Before you start the application: db_copy_table the rows it needs and "
                "use_scratch_database with these settings, or use_dev_database with them (the user approves)."
            )
        if self.on_dev_database:
            lines.append(
                f"The application's settings {', '.join(self.dev_variables)} point at the DEVELOPMENT database for "
                "this session (approved by the user): what it writes there is real and shared, its DELETE, "
                "TRUNCATE and DROP statements are refused, and its writes are reported to the user. "
                "use_dev_database with empty variables switches back."
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
