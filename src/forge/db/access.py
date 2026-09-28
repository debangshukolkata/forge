"""Detects what Forge may do on each database (spec §9.5.2): L3 write / L2 read-only / L1 no connection."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum

import psycopg

from forge.config import Secrets
from forge.db.connection import DbTarget, connect, explain_connection_error, safe_schema_name


class AccessLevel(StrEnum):
    WRITE = "L3"  # connect, introspect, read, create/drop its own objects in the scratch schema
    READ_ONLY = "L2"  # connect, introspect, read; cannot create
    NONE = "L1"  # no connection


@dataclass
class AccessReport:
    target: str
    level: AccessLevel
    reason: str
    scratch_schema: str | None = None
    scratch_exists: bool = False
    can_create_schema: bool = False
    can_write_elsewhere: list[str] | None = None  # schemas besides scratch where CREATE is allowed

    def line(self) -> str:
        where = (
            f", scratch schema {self.scratch_schema}" + ("" if self.scratch_exists else " (not created yet)")
            if self.scratch_schema and self.level != AccessLevel.NONE
            else ""
        )
        return f"{self.target} database: {self.level.value} ({self.reason}){where}"


def detect(target: DbTarget, secrets: Secrets, scratch_schema: str | None) -> AccessReport:
    try:
        connection = connect(target, secrets)
    except (psycopg.Error, OSError) as error:
        return AccessReport(target.name, AccessLevel.NONE, explain_connection_error(error), scratch_schema)
    with connection:
        row = connection.execute(
            "SELECT has_database_privilege(current_user, current_database(), 'CREATE')"
        ).fetchone()
        can_create_schema = bool(row and row[0])
        others = [
            row[0]
            for row in connection.execute(
                "SELECT nspname FROM pg_namespace WHERE nspname NOT LIKE 'pg\\_%' AND nspname <> "
                "'information_schema' "
                "AND has_schema_privilege(current_user, nspname, 'CREATE')"
            ).fetchall()
        ]
        if scratch_schema is None:
            level = AccessLevel.WRITE if can_create_schema else AccessLevel.READ_ONLY
            return AccessReport(
                target.name,
                level,
                "connected; no scratch schema chosen yet",
                None,
                False,
                can_create_schema,
                others,
            )
        schema = safe_schema_name(scratch_schema)
        exists = (
            connection.execute("SELECT 1 FROM pg_namespace WHERE nspname = %s", (schema,)).fetchone()
            is not None
        )
        report = AccessReport(
            target.name,
            AccessLevel.READ_ONLY,
            "connected, read-only",
            schema,
            exists,
            can_create_schema,
            [s for s in others if s != schema],
        )
        if exists and _can_create_and_drop(connection, schema):
            report.level, report.reason = (
                AccessLevel.WRITE,
                "connected; can create and drop objects in the scratch schema",
            )
        elif not exists:
            report.reason = "connected; the scratch schema doesn't exist yet"
            report.level = AccessLevel.WRITE if can_create_schema else AccessLevel.READ_ONLY
        return report


def _can_create_and_drop(connection: psycopg.Connection[object], schema: str) -> bool:
    """The only reliable test: actually create and drop a throw-away table in the scratch schema."""
    probe = f"forge_probe_{uuid.uuid4().hex[:8]}"
    try:
        connection.execute(f'CREATE TABLE "{schema}"."{probe}" (id integer)')
        connection.execute(f'DROP TABLE "{schema}"."{probe}"')
        return True
    except psycopg.Error:
        return False
