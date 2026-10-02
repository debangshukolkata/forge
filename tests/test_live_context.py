"""M4 live: the real model works through a task in a deliberately tiny context window, forcing
micro-compaction and a real summary. Run with: pytest -m live"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from forge.config import load_config, load_secrets
from forge.context.compaction import pairs_are_valid, summary_is_valid
from forge.engine.session_host import SessionHost
from forge.llm.router import LLMRouter
from forge.protocol.events import EventBus, EventType
from forge.protocol.inputs import SendMessage, SlashCommand
from forge.workspace.create import create_workspace
from tests.conftest import REPO_ROOT

pytestmark = pytest.mark.live
FILES = [
    "backend/claims_app/errors.py",
    "backend/claims_app/config.py",
    "backend/claims_app/bootstrap.py",
    "backend/claims_app/db.py",
    "backend/claims_app/auth.py",
    "backend/claims_app/llm.py",
    "backend/claims_app/graphs/triage_graph.py",
    "backend/claims_app/repositories/claims_repository.py",
]


async def wait_for_turn(host: SessionHost, since: int, timeout: float = 400) -> None:
    subscription = host.bus.subscribe(since_seq=since)
    try:
        async with asyncio.timeout(timeout):
            async for event in subscription:
                if event.type in (EventType.COST_UPDATED, EventType.ERROR):
                    return
    finally:
        subscription.close()


async def test_small_window_forces_compaction_and_the_task_still_completes(
    original_repo: Path, tmp_path: Path, isolated_forge_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FORGE_ENV_FILE", str(REPO_ROOT / ".env"))
    secrets = load_secrets(isolated_forge_home)
    if not secrets.get("AZURE_OPENAI_API_KEY"):
        pytest.skip("AZURE_OPENAI_* not configured in .env")
    config = load_config(isolated_forge_home)
    config.llm.models["gpt51"] = config.llm.models["gpt51"].model_copy(
        update={"context_window": 20_000, "max_output": 3_000}  # small, but not starved
    )
    config.context.keep_recent_turns = 4
    config.context.micro_compact_at = 0.2  # low thresholds make the automatic summary happen mid-task
    config.context.auto_compact_at = 0.25
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    host = SessionHost(
        LLMRouter(config, secrets), EventBus(workspace.forge_dir / "events.jsonl"), workspace=workspace
    )
    runner = asyncio.create_task(host.run())

    since = host.bus.last_seq
    await host.submit(
        SendMessage(
            text=(
                "Read each of these files with read_file, one call per file, one after another: "
                + ", ".join(FILES)
                + ". Then list every class name you saw, one per line."
            )
        )
    )
    await wait_for_turn(host, since)
    since = host.bus.last_seq
    await host.submit(SlashCommand(text="/compact focus on the class names found"))
    await asyncio.sleep(0.1)
    await host.submit(SendMessage(text="Which file defined NotFoundError? One line."))
    await wait_for_turn(host, since)
    await host.close()
    runner.cancel()

    events = host.bus.events_since(0)
    notices = [e.payload.get("kind") for e in events if e.type == EventType.NOTICE]
    errors = [e for e in events if e.type == EventType.ERROR]
    percents = [e.payload["percent"] for e in events if e.type == EventType.CONTEXT_UPDATED]
    answers = [e.payload["text"] for e in events if e.type == EventType.MESSAGE_DONE]

    assert errors == []
    assert notices.count("compacted") >= 2  # automatic during the task, then the /compact request
    reads = [e.payload["summary"] for e in events if e.type == EventType.TOOL_CALL_STARTED]
    # No thrash (D-055): in this deliberately tiny window a file may be re-read after a summary, but
    # never again and again (before D-055 the model looped until the step limit).
    # A runaway loop would re-read until the 40-step limit; repeated identical calls are stopped by the
    # M8 stuck detector (R26). Here we only check the loop stays bounded.
    assert max(reads.count(r) for r in set(reads)) <= 6
    assert host.context_manager.compactions >= 1
    assert summary_is_valid(host.context_manager.pinned.get("compaction_summary") or "")
    assert list((workspace.forge_dir / "compactions").glob("*.md"))
    assert max(percents) <= 100
    assert pairs_are_valid(host.history)
    assert "ClaimsAppError" in "\n".join(answers)
    assert "errors.py" in answers[-1]
