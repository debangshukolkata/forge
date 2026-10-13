"""P1.1: the contact sheet puts many slides in one numbered picture, and the preview tool offers it first."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
from PIL import Image

from forge.slides import preview
from forge.slides.contact_sheet import CELL_WIDTH, GAP, PER_SHEET, make_contact_sheets
from forge.toolkit.base import ToolContext
from forge.tools.presentation import PreviewPresentation
from forge.workspace.create import create_workspace


def _pictures(folder: Path, count: int, size: tuple[int, int] = (1600, 900)) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for number in range(1, count + 1):
        path = folder / f"slide-{number}.png"
        Image.new("RGB", size, (number * 15 % 255, 90, 160)).save(path)
        paths.append(path)
    return paths


def test_a_short_deck_is_one_sheet_with_the_right_size(tmp_path: Path) -> None:
    sheets = make_contact_sheets(_pictures(tmp_path, 5), tmp_path)
    assert [s.name for s in sheets] == ["contact-sheet-1.png"]
    with Image.open(sheets[0]) as image:
        cell_height = round(CELL_WIDTH * 900 / 1600)
        assert image.size == (3 * CELL_WIDTH + 4 * GAP, 2 * cell_height + 3 * GAP)  # 5 slides: 2 rows of 3


def test_a_long_deck_gets_several_sheets_and_old_sheets_are_replaced(tmp_path: Path) -> None:
    pictures = _pictures(tmp_path, PER_SHEET + 3)
    assert len(make_contact_sheets(pictures, tmp_path)) == 2
    assert len(make_contact_sheets(pictures[:4], tmp_path)) == 1
    assert [p.name for p in tmp_path.glob("contact-sheet-*.png")] == ["contact-sheet-1.png"]


def test_pictures_of_other_shapes_are_scaled_to_the_tile_width(tmp_path: Path) -> None:
    pictures = _pictures(tmp_path / "a", 1, (1200, 900)) + _pictures(tmp_path / "b", 1, (1600, 900))
    sheet = make_contact_sheets(pictures, tmp_path)[0]
    with Image.open(sheet) as image:
        assert image.width == 3 * CELL_WIDTH + 4 * GAP and image.height > 2 * GAP


@pytest.fixture
def context(tmp_path: Path, original_repo: Path) -> ToolContext:
    return ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))


def test_the_preview_tool_lists_the_contact_sheet_first(
    context: ToolContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    context.workspace.write_text(
        "docs/deck.pptx", "x"
    )  # only its name and suffix matter: the export is replaced
    seen: dict[str, Path] = {}

    def fake_export(deck: Path, folder: Path) -> list[Path]:
        seen["folder"] = folder
        return _pictures(folder, 4)

    monkeypatch.setattr(preview, "export_slides", fake_export)
    result = asyncio.run(PreviewPresentation().run(PreviewPresentation.Args(path="docs/deck.pptx"), context))
    assert result.ok
    assert result.content.index("contact-sheet-1.png") < result.content.index("slide-1.png")
    assert "look at these first" in result.content
    assert (seen["folder"] / "contact-sheet-1.png").is_file()
    json.dumps(result.content)
