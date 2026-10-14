"""Live (real Azure model): the critic picks a fitting design among three catalogue systems for a brief (D-350)."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.config import ForgeConfig, Secrets
from forge.toolkit.base import ToolContext
from forge.tools.design_candidates import DesignCandidates
from forge.workspace.create import create_workspace
from tests.test_live_llm import live, router_for  # noqa: F401  (the fixture and the router builder)

pytestmark = pytest.mark.live

SKILL = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "forge"
    / "skills"
    / "ui-design-quality"
    / "recipes"
    / "design-systems"
)


async def test_the_critic_prefers_the_playful_system_for_a_childrens_museum(
    live: tuple[ForgeConfig, Secrets],  # noqa: F811
    tmp_path: Path,
    original_repo: Path,
) -> None:
    pytest.importorskip("playwright.async_api")
    config, secrets = live
    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace, router=router_for(config, secrets))
    names = {"a": "ds-dark-dashboard", "b": "ds-playful-friendly", "c": "ds-minimal-monochrome"}
    for letter, name in names.items():
        workspace.write_text(
            f".forge/candidates/{letter}/DESIGN.md",
            (SKILL / f"{name}.design.md").read_text(encoding="utf-8"),
            "x",
        )
    result = await DesignCandidates().run(
        DesignCandidates.Args(
            brief="A website for a children's science museum: joyful, curious, welcoming to families with young kids.",
            candidates=[f".forge/candidates/{x}/DESIGN.md" for x in "abc"],
            headline="Come and wonder",
        ),
        context,
    )
    if not result.ok and "browser" in result.content:
        pytest.skip(result.content)
    assert result.ok, result.content
    assert "Winner: B" in result.content, result.content
