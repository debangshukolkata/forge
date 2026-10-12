"""Live (real Azure model): the design critic rejects an unstyled page and returns concrete fixes (D-249)."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.config import ForgeConfig, Secrets
from forge.subagents.critic import critic_verdict
from forge.subagents.spawn_tool import SpawnSubagent
from forge.toolkit.base import ToolContext
from forge.tools.browser import BrowserClose
from forge.workspace.create import create_workspace
from tests.test_live_llm import live, router_for  # noqa: F401  (the fixture and the router builder)
from tests.test_ui_audit import site  # noqa: F401

pytestmark = pytest.mark.live


async def test_the_critic_rejects_an_unstyled_page_with_concrete_fixes(
    live: tuple[ForgeConfig, Secrets],  # noqa: F811
    site: str,  # noqa: F811
    tmp_path: Path,
    original_repo: Path,
) -> None:
    pytest.importorskip("playwright.async_api")
    config, secrets = live
    router = router_for(config, secrets)
    context = ToolContext(
        workspace=create_workspace(original_repo, tmp_path / "ws", "backend"), router=router
    )
    context.step = 4
    try:
        result = await SpawnSubagent().run(
            SpawnSubagent.Args(
                agent="design-critic",
                task=f"Review {site}/unstyled.html: a landing page for a blood donation camp.",
            ),
            context,
        )
    finally:
        if context.browser is not None:
            await BrowserClose().run(BrowserClose.Args(), context)
    assert result.ok, result.content
    assert critic_verdict(result.content) == "REVISE", result.content
    assert "FIXES" in result.content and context.critic_rounds == 1 and not context.critic_ship
    assert context.last_critic_step == 4
