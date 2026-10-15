"""DIE4: the art director is a read-only subagent on the planner role that returns a DESIGN.md; it can run beside other readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from forge.agent.loop import PARALLEL_SUBAGENT_TYPES
from forge.config import Secrets
from forge.subagents import spawn_tool
from forge.subagents.art_director import ART_DIRECTOR_PROMPT
from forge.toolkit.base import ToolContext
from forge.tools.parity import BUILT_IN_TYPES
from forge.workspace.create import create_workspace


def test_the_art_director_is_a_known_parallel_safe_agent_with_a_complete_brief() -> None:
    assert "art-director" in BUILT_IN_TYPES and "art-director" in PARALLEL_SUBAGENT_TYPES
    for needed in (
        "design_kb_search",
        "view_image",
        "Page Composition",
        "Motion and Interaction",
        "Accessibility",
        "KEEP FIXED",
        "because",
    ):
        assert needed in ART_DIRECTOR_PROMPT


async def test_it_runs_on_the_planner_role_with_read_only_tools(
    original_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict[str, Any] = {}

    async def fake(
        router: Any, context: Any, tools: Any, prompt: str, task: str, steps: int, role: str, **kwargs: Any
    ) -> str:
        seen.update(
            role=role,
            prompt=prompt,
            tools=set(tools._tools),
        )
        return "DIRECTION: calm"

    monkeypatch.setattr(spawn_tool, "_run_subagent", fake)
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, secrets=Secrets({}, None))
    context.router = object()  # type: ignore[assignment]
    result = await spawn_tool.SpawnSubagent().run(
        spawn_tool.SpawnSubagent.Args(agent="art-director", task="A pottery studio site"), context
    )
    assert result.ok and "DIRECTION: calm" in result.content
    assert seen["role"] == "planner" and seen["prompt"] == ART_DIRECTOR_PROMPT
    assert {"view_image", "design_kb_search"} <= seen["tools"]
    assert not seen["tools"] & {"write_file", "edit_file", "run_command"}
