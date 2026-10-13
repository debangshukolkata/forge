"""P2.18: text and tables measured by PowerPoint itself decide what overflows; without PowerPoint the estimate stays."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from forge.slides import preview
from forge.slides.build import build_deck
from forge.slides.measure import Measure, measure_deck, overflow_problems, parse_measures
from forge.slides.spec import parse_deck
from forge.toolkit.base import ToolContext
from forge.tools.presentation import PreviewPresentation
from forge.workspace.create import create_workspace


def _measure(**kw: object) -> Measure:
    base = dict(
        slide=1,
        name="TextBox 2",
        kind="text",
        left=72,
        top=144,
        width=216,
        height=36,
        slide_width=960,
        slide_height=540,
    )
    return Measure(**{**base, **kw})  # type: ignore[arg-type]


def test_text_taller_than_its_box_is_reported_in_inches() -> None:
    problems = overflow_problems([_measure(text_height=96, text="a very long line")])
    assert (
        len(problems) == 1
        and "1.33 in tall but its box has 0.50 in" in problems[0]
        and "'a very long line'" in problems[0]
    )


def test_text_that_fits_or_only_rounds_over_is_not_reported() -> None:
    assert overflow_problems([_measure(text_height=36), _measure(text_height=36 + 2)]) == []
    assert overflow_problems([_measure(text_height=20, margins=(3.6, 3.6, 7.2, 7.2))]) == []


def test_margins_reduce_the_room() -> None:
    assert overflow_problems([_measure(text_height=34, margins=(7.2, 7.2, 0, 0))])  # 34 pt in 21.6 pt of room


def test_a_word_wider_than_the_box_is_reported() -> None:
    assert "wider than its box" in overflow_problems([_measure(text_height=10, text_width=300)])[0]


def test_tables_and_boxes_past_the_slide_edge_are_reported() -> None:
    table = _measure(kind="table", name="Table 4", top=300, height=360, text_height=0)
    assert "table grew past the slide edge" in overflow_problems([table])[0]
    wide = _measure(left=900, width=216, text_height=10)
    assert "past the slide edge" in overflow_problems([wide])[0]
    assert overflow_problems([_measure(kind="table", top=100, height=300)]) == []


def test_the_measure_output_parses_including_a_single_object() -> None:
    row = {
        "slide": 2,
        "name": "T",
        "left": 1,
        "top": 2,
        "width": 3,
        "height": 4,
        "kind": "text",
        "slideWidth": 960,
        "slideHeight": 540,
        "textHeight": 5,
        "marginTop": 3.6,
    }
    assert parse_measures(json.dumps([row]))[0].margins[0] == 3.6
    assert parse_measures(json.dumps(row))[0].text_height == 5  # PowerShell prints one object without a list


needs_powerpoint = pytest.mark.skipif(not preview.available(), reason="PowerPoint is not installed here")


@needs_powerpoint
def test_powerpoint_finds_a_real_overflow_and_a_table_that_grew(tmp_path: Path) -> None:
    deck = {
        "title": "M",
        "slides": [
            {
                "layout": "freeform",
                "title": "Overflow is found by measuring",
                "elements": [
                    {
                        "type": "text",
                        "x": 1,
                        "y": 2,
                        "w": 3,
                        "h": 0.5,
                        "autofit": False,
                        "size": 20,
                        "text": "This is a long paragraph that cannot possibly fit into a box half an inch high",
                    },
                    {
                        "type": "text",
                        "x": 6,
                        "y": 2,
                        "w": 5,
                        "h": 1.2,
                        "text": "This one fits comfortably",
                        "size": 20,
                    },
                    {
                        "type": "table",
                        "x": 1,
                        "y": 4,
                        "w": 6,
                        "h": 2,
                        "columns": ["A", "B"],
                        "rows": [[i, "x"] for i in range(14)],
                    },
                ],
            }
        ],
    }
    path = tmp_path / "m.pptx"
    path.write_bytes(build_deck(parse_deck(json.dumps(deck)), lambda n: b"").data)
    problems = overflow_problems(measure_deck(path))
    assert any("This is a long paragraph" in p for p in problems) and any(
        "table grew past" in p for p in problems
    )
    assert not any("fits comfortably" in p for p in problems)


@needs_powerpoint
def test_a_deck_built_with_the_normal_layouts_measures_clean(tmp_path: Path) -> None:
    deck = {
        "title": "Deck",
        "slides": [
            {"layout": "title", "title": "Q3 review"},
            {
                "layout": "bullets",
                "title": "We shipped three things this quarter",
                "bullets": ["Search is faster", "Billing is simpler", "Mobile launched"],
            },
            {
                "layout": "stats",
                "title": "Weekly users grew 42%",
                "items": [{"value": "42%", "label": "growth"}, {"value": "1.2M", "label": "users"}],
            },
        ],
    }
    path = tmp_path / "d.pptx"
    path.write_bytes(build_deck(parse_deck(json.dumps(deck)), lambda n: b"").data)
    assert overflow_problems(measure_deck(path)) == []


def test_the_preview_tool_reports_what_powerpoint_measured(
    tmp_path: Path, original_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    context.workspace.write_text("docs/deck.pptx", "x")
    monkeypatch.setattr(preview, "export_slides", lambda deck, folder: [])
    monkeypatch.setattr("forge.tools.presentation.make_contact_sheets", lambda *a, **k: [])
    monkeypatch.setattr(
        "forge.tools.presentation.measure_deck", lambda deck: [_measure(text_height=96, text="Too long")]
    )
    result = asyncio.run(PreviewPresentation().run(PreviewPresentation.Args(path="docs/deck.pptx"), context))
    assert "PowerPoint measured text that does not fit" in result.content and "Too long" in result.content
    monkeypatch.setattr("forge.tools.presentation.measure_deck", lambda deck: [_measure(text_height=20)])
    clean = asyncio.run(PreviewPresentation().run(PreviewPresentation.Args(path="docs/deck.pptx"), context))
    assert "all fit their space" in clean.content
    monkeypatch.setattr(
        "forge.tools.presentation.measure_deck",
        lambda deck: (_ for _ in ()).throw(preview.PreviewUnavailable("no")),
    )
    quiet = asyncio.run(PreviewPresentation().run(PreviewPresentation.Args(path="docs/deck.pptx"), context))
    assert "measured" not in quiet.content
