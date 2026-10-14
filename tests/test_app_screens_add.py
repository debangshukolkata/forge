"""D-366: add_asset copies an application screen into the project (a separate file: the browser tests there hold a running event loop)."""

from __future__ import annotations

from pathlib import Path


async def test_a_screen_is_copied_into_the_project(original_repo: Path, tmp_path: Path) -> None:
    from forge.toolkit.base import ToolContext
    from forge.tools.assets import AddAsset
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_text(
        "DESIGN.md", "# Brand guide", "the design gate wants a DESIGN.md before a page is added"
    )
    context = ToolContext(workspace=workspace)
    added = await AddAsset().run(AddAsset.Args(id="app-table-data"), context)
    assert added.ok, added.content
    assert "bulk" in workspace.path_of("screens/table-data.html").read_text(encoding="utf-8").lower()


def test_the_prompts_and_the_skill_send_applications_to_the_screen_recipes() -> None:
    root = Path(__file__).resolve().parents[1] / "src" / "forge"
    for relative in ("agent/prompts/system.md", "agent/prompts/system_modeb.md"):
        assert "Applications are built from screen recipes" in (root / relative).read_text(encoding="utf-8")
    skill = (root / "skills/ui-design-quality/SKILL.md").read_text(encoding="utf-8")
    assert "## 0i. Applications: start from a screen recipe" in skill and "app-dashboard-kpi" in skill
