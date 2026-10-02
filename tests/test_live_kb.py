"""M5 live: the real kb_builder model writes the narrative docs; the agent then answers from the KB.
Run with: pytest -m live"""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path

import pytest

from forge.cli import main
from forge.config import load_config, load_secrets
from forge.engine.session_host import SessionHost
from forge.kb.store import kb_dir_for
from forge.llm.router import LLMRouter
from forge.protocol.events import EventBus, EventType
from forge.protocol.inputs import SendMessage
from forge.workspace.create import create_workspace
from tests.conftest import FIXTURE_REPO, REPO_ROOT

pytestmark = pytest.mark.live


@pytest.fixture
def live_home(isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    if not load_secrets(isolated_forge_home).get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    return isolated_forge_home


async def test_kb_build_and_agent_uses_it(live_home: Path, tmp_path: Path) -> None:
    repo = tmp_path / "claims-repo"
    shutil.copytree(FIXTURE_REPO, repo, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.db"))

    assert await asyncio.to_thread(main, ["kb", "build", "--repo", str(repo), "--app-folder", "backend"]) == 0
    kb_dir = kb_dir_for(live_home, repo, "backend")
    architecture = (kb_dir / "ARCHITECTURE.md").read_text(encoding="utf-8")
    conventions = (kb_dir / "CONVENTIONS.md").read_text(encoding="utf-8")
    module = (kb_dir / "modules" / "claims_app.repositories.md").read_text(encoding="utf-8")

    assert "create_app" in architecture and "app_config" in architecture
    assert "## Top conventions" in conventions
    assert "## Purpose" in module and "claims_repository" in module
    assert "Top conventions" in (kb_dir / "ESSENTIALS.md").read_text(encoding="utf-8")
    assert (
        await asyncio.to_thread(main, ["kb", "status", "--repo", str(repo), "--app-folder", "backend"]) == 0
    )

    workspace = create_workspace(repo, tmp_path / "ws", "backend")
    config, secrets = load_config(live_home), load_secrets(live_home)
    host = SessionHost(
        LLMRouter(config, secrets), EventBus(workspace.forge_dir / "events.jsonl"), workspace=workspace
    )
    runner = asyncio.create_task(host.run())
    await host.submit(
        SendMessage(
            text="Which HTTP endpoint triages a claim, and which class implements it? "
            "Use the knowledge base. Answer in one line."
        )
    )
    subscription = host.bus.subscribe()
    async with asyncio.timeout(240):
        async for event in subscription:
            if event.type in (EventType.COST_UPDATED, EventType.ERROR):
                break
    subscription.close()
    await host.close()
    runner.cancel()

    events = host.bus.events_since(0)
    tools = [e.payload["name"] for e in events if e.type == EventType.TOOL_CALL_STARTED]
    answer = [e.payload["text"] for e in events if e.type == EventType.MESSAGE_DONE][-1]
    assert any(name in ("kb_search", "kb_read", "find_symbol") for name in tools)
    assert re.search(r"/api/claims/[<{:(]*(?:int:)?\s*claim_id[>})]*/triage", answer), answer
    assert "ClaimTriage" in answer
