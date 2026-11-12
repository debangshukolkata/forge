"""The database: agents, tools and which agent has which tool."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from agenthub import settings


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
    tools: list[Tool]


def connect() -> sqlite3.Connection:
    fresh = not settings.DATABASE.exists()
    settings.DATABASE.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.DATABASE)
    if fresh:
        connection.executescript((Path(__file__).parent / "seed.sql").read_text(encoding="utf-8"))
        connection.commit()
    return connection


def agent_names() -> list[str]:
    with connect() as connection:
        return [row[0] for row in connection.execute("SELECT name FROM agents ORDER BY name")]


def load_agent(name: str) -> Agent | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT name, purpose, max_context_chars FROM agents WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return None
        tools = [
            Tool(*tool_row)
            for tool_row in connection.execute(
                "SELECT t.name, t.kind, t.description, t.target FROM tools t "
                "JOIN agent_tools a ON a.tool = t.name WHERE a.agent = ? ORDER BY t.name",
                (name,),
            )
        ]
    return Agent(row[0], row[1], row[2], tools)
