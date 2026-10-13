"""L10 (D-313): templates come with reference pictures the model can look at."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.toolkit.base import ToolContext
from forge.tools.assets import AddAsset, FindAsset
from forge.workspace.create import create_workspace

SKILL = Path(__file__).resolve().parents[1] / "src" / "forge" / "skills" / "ui-design-quality"
TEMPLATES = sorted(p.stem for p in (SKILL / "assets" / "template").glob("*.md"))


@pytest.mark.parametrize("template", TEMPLATES)
def test_every_template_has_a_desktop_and_a_phone_picture(template: str) -> None:
    for label in ("desktop", "mobile"):
        picture = SKILL / "assets" / "preview" / f"{template}-{label}.jpg"
        assert picture.is_file() and 20_000 < picture.stat().st_size < 400_000, picture


async def test_find_asset_says_a_template_has_pictures_and_add_asset_copies_them(
    original_repo: Path, tmp_path: Path
) -> None:
    context = ToolContext(
        workspace=create_workspace(original_repo, tmp_path / "ws", "backend"), design_first=False
    )
    found = await FindAsset().run(FindAsset.Args(query="saas landing page", type="template"), context)
    assert found.ok and "tpl-landing-saas" in found.content and "reference pictures" in found.content
    added = await AddAsset().run(AddAsset.Args(id="tpl-landing-saas", project_dir="web"), context)
    assert (
        added.ok
        and ".forge/reference/tpl-landing-saas-desktop.jpg" in added.content
        and "view_image" in added.content
    )
    copied = context.workspace.root / ".forge" / "reference" / "tpl-landing-saas-desktop.jpg"
    assert copied.is_file() and copied.read_bytes()[:3] == b"\xff\xd8\xff"  # a real JPEG


async def test_an_asset_without_pictures_adds_no_reference_line(original_repo: Path, tmp_path: Path) -> None:
    context = ToolContext(
        workspace=create_workspace(original_repo, tmp_path / "ws", "backend"), design_first=False
    )
    found = await FindAsset().run(FindAsset.Args(query="marquee", type="effect"), context)
    assert found.ok and "reference pictures" not in found.content
