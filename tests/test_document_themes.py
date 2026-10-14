"""D-375: documents use the deck themes through `brand_file: theme:<name>`, so a report and its deck look alike."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge.brand.kit import BrandError, Resolved, contrast
from forge.slides.themes import THEMES
from forge.toolkit.base import ToolContext
from forge.tools.brand_file import load_brand_file, theme_kit


def test_every_deck_theme_is_a_readable_brand_kit() -> None:
    for name, theme in THEMES.items():
        kit = theme_kit(name)
        resolved = Resolved(kit)
        assert kit.accent == theme.accent and kit.title_font == theme.title_font
        assert contrast(resolved.text or "111111", "FFFFFF") >= 4.5, (
            name
        )  # printed on white paper, also for the dark deck themes
        assert contrast(resolved.header_text or "FFFFFF", resolved.header_fill or "1F3864") >= 4.5, name


def test_an_unknown_theme_lists_the_known_ones() -> None:
    with pytest.raises(BrandError, match="clean"):
        theme_kit("nope")


async def test_a_theme_prefix_replaces_a_brand_file(original_repo: Path, tmp_path: Path) -> None:
    from forge.workspace.create import create_workspace

    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    kit = load_brand_file(context, "theme:Dark")
    assert kit is not None and kit.accent == THEMES["dark"].accent
    assert load_brand_file(context, "") is None
