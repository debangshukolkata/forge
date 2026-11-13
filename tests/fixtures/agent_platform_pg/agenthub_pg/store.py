"""The database (PostgreSQL): agents, their system prompts, tools and which agent has which tool."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import psycopg

from agenthub_pg.settings import settings


@dataclass
class Tool:
    name: str
    kind: str
    description: str
    target: str


@dataclass
class Agent:
    name: str
    purpose: str
    max_context_chars: int
    system_prompt: str
    tools: list[Tool]


def connect() -> psycopg.Connection:
    return psycopg.connect(
        settings.database_url, options=f"-c search_path={settings.schema_name}", autocommit=True
    )


def ensure_seeded() -> None:
    """Creates and fills the tables the first time (a fresh schema)."""
    with connect() as connection:
        if connection.execute("SELECT to_regclass('agents')").fetchone()[0] is None:  # type: ignore[index]
            connection.execute((Path(__file__).parent / "seed.sql").read_text(encoding="utf-8"))


def applications() -> list[object]:
    """The documents of the `applications` table, in name order."""
    with connect() as connection:
        return [row[0] for row in connection.execute("SELECT doc FROM applications ORDER BY name")]


def record_run(agent: str, status: str) -> None:
    """One row per run in the `runs` table (a read-only database refuses it: the run then fails)."""
    with connect() as connection:
        connection.execute("INSERT INTO runs (agent, status) VALUES (%s, %s)", (agent, status))


def agent_names() -> list[str]:
    with connect() as connection:
        return [row[0] for row in connection.execute("SELECT name FROM agents ORDER BY name")]


def load_agent(name: str) -> Agent | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT name, purpose, max_context_chars, system_prompt FROM agents WHERE name = %s", (name,)
        ).fetchone()
        if row is None:
            return None
        tools = [
            Tool(*tool_row)
            for tool_row in connection.execute(
                "SELECT t.name, t.kind, t.description, t.target FROM tools t "
                "JOIN agent_tools a ON a.tool = t.name WHERE a.agent = %s ORDER BY t.name",
                (name,),
            )
        ]
    return Agent(*row, tools)
