"""Live schema introspection (spec §9.5 db_schema, §11.2 DB_SCHEMA): tables, columns, keys, indexes.
Read-only session; deny-listed (credentials) tables show column names only — never rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import psycopg

from forge.config import Secrets
from forge.db.connection import DbTarget, connect, safe_schema_name


@dataclass
class ColumnInfo:
    name: str
    type: str
    nullable: bool
    default: str | None


@dataclass
class TableInfo:
    schema: str
    name: str
    columns: list[ColumnInfo] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    foreign_keys: list[str] = field(default_factory=list)
    indexes: list[str] = field(default_factory=list)


def introspect(
    target: DbTarget, secrets: Secrets, schema: str = "public", table: str | None = None
) -> list[TableInfo]:
    schema = safe_schema_name(schema)
    with connect(target, secrets, read_only=True) as connection:
        return _tables(connection, schema, table)


def _tables(connection: psycopg.Connection[Any], schema: str, only: str | None) -> list[TableInfo]:
    names = [
        r[0]
        for r in connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s AND "
            "table_type = 'BASE TABLE' "
            "AND (%s::text IS NULL OR table_name = %s) ORDER BY table_name",
            (schema, only, only),
        ).fetchall()
    ]
    tables = []
    for name in names:
        info = TableInfo(schema, name)
        for column, data_type, nullable, default in connection.execute(
            "SELECT column_name, data_type, is_nullable = 'YES', column_default FROM "
            "information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (schema, name),
        ):
            info.columns.append(ColumnInfo(column, data_type, nullable, default))
        info.primary_key = [
            r[0]
            for r in connection.execute(
                "SELECT a.attname FROM pg_index i JOIN pg_attribute a ON a.attrelid = i.indrelid "
                "AND a.attnum = ANY(i.indkey) "
                "WHERE i.indrelid = %s::regclass AND i.indisprimary",
                (f'"{schema}"."{name}"',),
            ).fetchall()
        ]
        info.foreign_keys = [
            r[0]
            for r in connection.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = %s::regclass "
                "AND contype = 'f'",
                (f'"{schema}"."{name}"',),
            ).fetchall()
        ]
        info.indexes = [
            r[0]
            for r in connection.execute(
                "SELECT indexdef FROM pg_indexes WHERE schemaname = %s AND tablename = %s", (schema, name)
            ).fetchall()
        ]
        tables.append(info)
    return tables


def describe(tables: list[TableInfo], deny_tables: list[str]) -> str:
    if not tables:
        return "No tables found."
    lines = []
    for table in tables:
        secret = (
            " — credentials table: column names only, rows are never read"
            if table.name in deny_tables
            else ""
        )
        lines.append(f"### {table.schema}.{table.name}{secret}")
        for column in table.columns:
            flags = ["PK"] if column.name in table.primary_key else []
            flags += [] if column.nullable else ["NOT NULL"]
            default = f" default {column.default}" if column.default and not secret else ""
            lines.append(
                f"- `{column.name}` {column.type}" + (f" ({', '.join(flags)})" if flags else "") + default
            )
        lines += [f"- FK: {fk}" for fk in table.foreign_keys]
        lines += [f"- index: {ix}" for ix in table.indexes if "_pkey" not in ix]
        lines.append("")
    return "\n".join(lines)
