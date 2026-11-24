"""D-654: a subagent never waits for an approval nobody can see."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from forge.protocol.approvals import ApprovalBroker, NobodyAnswers
from forge.protocol.events import EventBus
from forge.subagents import subagent
from forge.toolkit.base import ToolContext
from forge.tools.files import ReadFile
from forge.tools.registry import ToolRegistry
from forge.workspace.create import create_workspace


async def test_without_a_user_the_request_is_declined_at_once() -> None:
    answer = await asyncio.wait_for(NobodyAnswers(EventBus()).request({"tool": "run_command"}), 1)
    assert not answer.approved and "report it" in str(answer.instruction)


@pytest.mark.parametrize("connected", [True, False])
async def test_every_subagent_asks_through_the_main_channel(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, connected: bool
) -> None:
    used: list[Any] = []

    class Loop:
        def __init__(self, *args: Any) -> None:
            used.extend([args[5], args[4].mode])

    async def run(*args: Any) -> None:
        return None

    monkeypatch.setattr(subagent, "AgentLoop", Loop)
    monkeypatch.setattr(subagent, "ContextManager", lambda *a: None)
    monkeypatch.setattr(subagent, "_tracked_run", run)
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    host = SimpleNamespace(
        approvals=ApprovalBroker(EventBus()),
        agent=SimpleNamespace(gate=SimpleNamespace(mode="auto", ask_new_domains=False)),
    )
    if connected:
        context.interaction = SimpleNamespace(host=host)  # type: ignore[assignment]
    router: Any = SimpleNamespace(config=None)
    await subagent._run_subagent(router, context, ToolRegistry([ReadFile()]), "p", "t", 3, "coder")
    if connected:
        assert used == [host.approvals, "auto"]
    else:
        assert isinstance(used[0], NobodyAnswers)
