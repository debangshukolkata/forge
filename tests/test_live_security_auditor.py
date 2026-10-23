"""Live (real Azure model): the security auditor reports a SQL injection with evidence, and passes clean code (D-475)."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.config import ForgeConfig, Secrets
from forge.subagents.review import parse_review
from forge.subagents.spawn_tool import SpawnSubagent
from forge.toolkit.base import ToolContext
from forge.workspace.create import create_workspace
from tests.test_live_llm import live, router_for  # noqa: F401  (the fixture and the router builder)

pytestmark = pytest.mark.live

VULNERABLE = """import sqlite3


def find_user(connection: sqlite3.Connection, name: str):
    return connection.execute(f"SELECT * FROM users WHERE name = '{name}'").fetchall()
"""
SAFE = """import sqlite3


def find_user(connection: sqlite3.Connection, name: str):
    return connection.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchall()
"""


async def _audit(
    live_pair: tuple[ForgeConfig, Secrets], tmp_path: Path, original_repo: Path, text: str
) -> str:
    config, secrets = live_pair
    context = ToolContext(
        workspace=create_workspace(original_repo, tmp_path / "ws", "backend"),
        router=router_for(config, secrets),
    )
    context.workspace.path_of("backend/users_store.py").write_text(text, encoding="utf-8")
    result = await SpawnSubagent().run(
        SpawnSubagent.Args(agent="security-auditor", task="Audit backend/users_store.py."), context
    )
    assert result.ok, result.content
    return result.content


async def test_sql_injection_is_a_blocking_finding_with_evidence(
    live: tuple[ForgeConfig, Secrets],  # noqa: F811
    tmp_path: Path,
    original_repo: Path,
) -> None:
    report = await _audit(live, tmp_path, original_repo, VULNERABLE)
    blocking = [f for f in parse_review(report) if f.blocking]
    assert blocking, report
    assert "users_store.py" in blocking[0].text and "SELECT" in blocking[0].text, report
    assert "VERDICT: changes needed" in report


async def test_parameterised_sql_is_not_blocked(
    live: tuple[ForgeConfig, Secrets],  # noqa: F811
    tmp_path: Path,
    original_repo: Path,
) -> None:
    report = await _audit(live, tmp_path, original_repo, SAFE)
    assert not [f for f in parse_review(report) if f.blocking], report
