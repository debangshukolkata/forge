"""M7 live acceptance: the real model does database work through Forge's DB tools. Run with: pytest -m live

- L3 (local Postgres): the agent writes a migration following the repo's convention and tries it in the
  scratch schema; nothing outside the scratch schema changes.
- L1 (unreachable server): Forge reports L1, and the agent hands the DB step to the user (DB request) or
  marks the DB check server-run instead of claiming it ran.
"""

from __future__ import annotations

from pathlib import Path

import psycopg
import pytest
from dotenv import dotenv_values

from forge.config import Secrets, load_config, load_secrets
from forge.db.checks import load_checks
from forge.db.scratch import ScratchRegistry
from forge.engine.events import Event, EventBus, EventType
from forge.engine.inputs import Approve, UserInput
from forge.engine.session_host import SessionHost
from forge.llm.router import LLMRouter
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT
from tests.test_live_agent import events_of, run_turn

pytestmark = pytest.mark.live

REQUEST = (
    "Add a new SQL migration to backend/sql that adds a nullable `notes text` column to the claims table. "
    "Follow the existing file naming, numbering and style there (idempotent, with a commented rollback "
    "section). Then check that it works against a real database using the database tools available to you, "
    "and tell me where it was checked."
)

PUBLIC_TABLES = "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"


def approve_all(event: Event) -> UserInput | None:
    if event.type == EventType.APPROVAL_REQUESTED:
        return Approve(request_id=event.payload["id"])
    return None


def _host(original_repo: Path, tmp_path: Path, home: Path, secrets: Secrets) -> SessionHost:
    workspace = create_workspace(original_repo, tmp_path / "ws_db", "backend")
    return SessionHost(
        LLMRouter(load_config(home), secrets),
        EventBus(workspace.forge_dir / "events.jsonl"),
        workspace=workspace,
        secrets=secrets,
    )


def _live_secrets(home: Path, monkeypatch: pytest.MonkeyPatch) -> Secrets:
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    secrets = load_secrets(home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    return secrets


def _migration(host: SessionHost) -> str:
    assert host.workspace is not None
    new = sorted((host.workspace.repo_dir / "backend" / "sql").glob("V004__*.sql"))
    assert new, "no V004__*.sql migration was written"
    return new[0].read_text(encoding="utf-8")


def _tools_used(host: SessionHost) -> list[str]:
    return [e.payload.get("name", "") for e in events_of(host, EventType.TOOL_CALL_STARTED)]


async def test_migration_is_tried_in_the_scratch_schema(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    secrets = _live_secrets(isolated_forge_home, monkeypatch)
    admin_url = secrets.get("LOCAL_PG_URL")
    if not admin_url:
        pytest.skip("LOCAL_PG_URL not configured in .env")
    host = _host(original_repo, tmp_path, isolated_forge_home, secrets)
    assert host.db is not None
    with psycopg.connect(admin_url) as connection:
        public_before = connection.execute(PUBLIC_TABLES).fetchall()
    try:
        await run_turn(host, REQUEST, approve_all)
        migration = _migration(host)
        assert "notes" in migration.lower() and "if not exists" in migration.lower()
        assert "scratch_exec" in _tools_used(host)
        assert host.db.scratch is not None
        recorded = ScratchRegistry(isolated_forge_home).objects(host.db.scratch.key)
        assert ("table", "claims") in recorded, recorded
        with psycopg.connect(admin_url) as connection:
            public_after = connection.execute(PUBLIC_TABLES).fetchall()
        assert public_after == public_before
    finally:
        if host.db.scratch is not None:
            host.db.scratch.cleanup()


async def test_without_a_database_the_step_is_handed_over_not_claimed(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    live = _live_secrets(isolated_forge_home, monkeypatch)
    values = {k: v for k, v in dotenv_values(REPO_ROOT / ".env").items() if v}
    values["LOCAL_PG_URL"] = "postgresql://forge:x@127.0.0.1:1/none"  # check_secrets: fake
    monkeypatch.delenv("LOCAL_PG_URL", raising=False)
    secrets = Secrets(values, live.source)
    host = _host(original_repo, tmp_path, isolated_forge_home, secrets)
    assert host.db is not None

    await run_turn(host, REQUEST, approve_all)

    assert host.db.reports["local"].level.value == "L1"
    assert "L1" in (host.context_manager.pinned.get("database") or "")
    _migration(host)
    handed_over = bool(host.db.requests.all()) or bool(load_checks(host.workspace))  # type: ignore[arg-type]
    assert handed_over, f"tools used: {_tools_used(host)}"
    assert "scratch_exec" not in _tools_used(host) or host.db.scratch is None
