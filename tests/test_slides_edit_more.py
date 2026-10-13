"""The full-strength edit operations (D-289, TODO P2.12), on real decks."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("pptx")
from PIL import Image

from forge.slides.edit import apply_operations, parse_operations
from forge.slides.open_deck import DeckError, save_deck
from forge.slides.validate import validate_package
from tests.test_slides_edit import _deck


def _run(deck: Any, operations: list[dict[str, Any]], read_image: Any = None) -> list[str]:
    return apply_operations(deck, parse_operations(operations), read_image)


def _valid(deck: Any) -> None:
    assert not validate_package(save_deck(deck))


def _shape(slide: Any, kind: str) -> Any:
    return next(s for s in slide.shapes if getattr(s, kind, False))


def test_replace_picture_keeps_crop_and_place(tmp_path: Path) -> None:
    deck = _deck(tmp_path)
    picture = next(s for s in deck.slides[4].shapes if s.shape_type == 13)
    picture.crop_left = 0.1
    before = (picture.left, picture.top, picture.width, picture.height)
    buffer = io.BytesIO()
    Image.new("RGB", (80, 40), (200, 30, 30)).save(buffer, "PNG")
    _run(
        deck,
        [{"op": "replace_picture", "slide": 5, "shape": picture.shape_id, "image": "new.png"}],
        lambda n: buffer.getvalue(),
    )
    picture = next(s for s in deck.slides[4].shapes if s.shape_type == 13)
    assert (picture.left, picture.top, picture.width, picture.height) == before
    assert abs(picture.crop_left - 0.1) < 0.001
    assert picture.image.size == (80, 40)
    _valid(deck)


def test_format_text_one_phrase_or_everything(tmp_path: Path) -> None:
    deck = _deck(tmp_path)
    _run(
        deck, [{"op": "format_text", "slide": 2, "find": "SSO", "bold": True, "color": "#CC0000", "size": 30}]
    )
    runs = [
        r for s in deck.slides[1].shapes if s.has_text_frame for p in s.text_frame.paragraphs for r in p.runs
    ]
    sso = [r for r in runs if r.text == "SSO"]
    assert sso and sso[0].font.bold and str(sso[0].font.color.rgb) == "CC0000" and sso[0].font.size.pt == 30
    assert all(not r.font.bold for r in runs if r.text == "Faster search")
    _run(deck, [{"op": "format_text", "font": "Georgia"}])
    assert all(
        r.font.name == "Georgia"
        for s in deck.slides[1].shapes
        if s.has_text_frame
        for p in s.text_frame.paragraphs
        for r in p.runs
    )
    with pytest.raises(DeckError, match="no text matched"):
        _run(deck, [{"op": "format_text", "find": "zzz", "bold": True}])
    with pytest.raises(DeckError, match="at least one"):
        _run(deck, [{"op": "format_text"}])
    _valid(deck)


def test_format_text_inside_a_split_word_and_find_by_text(tmp_path: Path) -> None:
    deck = _deck(tmp_path)
    _run(
        deck,
        [{"op": "format_text", "slide": 2, "shape": "text:faster search", "find": "Faster", "italic": True}],
    )
    paragraph = next(
        p
        for s in deck.slides[1].shapes
        if s.has_text_frame
        for p in s.text_frame.paragraphs
        if "Faster" in p.text
    )
    assert paragraph.text == "Faster search"
    assert paragraph.runs[0].font.italic is True and not paragraph.runs[1].font.italic


def test_theme_fonts_and_colours(tmp_path: Path) -> None:
    deck = _deck(tmp_path)
    done = _run(
        deck,
        [
            {
                "op": "set_theme",
                "heading_font": "Georgia",
                "body_font": "Verdana",
                "colors": {"accent1": "#AA3355", "dk2": "112233"},
            }
        ],
    )
    xml = save_deck(deck)
    import zipfile

    theme = zipfile.ZipFile(io.BytesIO(xml)).read("ppt/theme/theme1.xml").decode()
    assert (
        "Georgia" in theme and "Verdana" in theme and 'val="AA3355"' in theme and "<a:dk2><a:srgbClr" in theme
    )
    assert "heading font" in done[0]
    with pytest.raises(DeckError, match="names are"):
        _run(deck, [{"op": "set_theme", "colors": {"bogus": "112233"}}])


def test_table_rows_and_columns(tmp_path: Path) -> None:
    deck = _deck(tmp_path)
    table_shape = _shape(deck.slides[3], "has_table")
    table = table_shape.table
    width = sum(c.width for c in table.columns)
    height = table_shape.height
    _run(
        deck,
        [
            {
                "op": "add_table_row",
                "slide": 4,
                "shape": table_shape.shape_id,
                "row": 3,
                "values": ["Docs", "Mei"],
            }
        ],
    )
    assert len(table.rows) == 4 and table.cell(2, 0).text == "Docs" and table.cell(3, 0).text == "Export"
    assert table_shape.height > height
    _run(
        deck,
        [
            {
                "op": "add_table_column",
                "slide": 4,
                "shape": table_shape.shape_id,
                "column": 3,
                "values": ["Due", "Mon", "Tue", "Wed"],
            }
        ],
    )
    assert len(table.columns) == 3 and table.cell(0, 2).text == "Due" and table.cell(3, 2).text == "Wed"
    assert abs(sum(c.width for c in table.columns) - width) < 5
    _run(
        deck,
        [
            {"op": "delete_table_row", "slide": 4, "shape": table_shape.shape_id, "row": 2},
            {"op": "delete_table_column", "slide": 4, "shape": table_shape.shape_id, "column": 1},
        ],
    )
    assert len(table.rows) == 3 and len(table.columns) == 2 and table.cell(1, 0).text == "Mei"
    with pytest.raises(DeckError, match="no row 9"):
        _run(deck, [{"op": "delete_table_row", "slide": 4, "shape": table_shape.shape_id, "row": 9}])
    _valid(deck)


def test_chart_type_and_format(tmp_path: Path) -> None:
    deck = _deck(tmp_path)
    chart_shape = _shape(deck.slides[2], "has_chart")
    name = chart_shape.name
    _run(deck, [{"op": "change_chart_type", "slide": 3, "shape": chart_shape.shape_id, "kind": "line"}])
    chart_shape = _shape(deck.slides[2], "has_chart")
    assert chart_shape.name == name and chart_shape.chart.chart_type.name.startswith("LINE")
    assert list(chart_shape.chart.plots[0].categories) == ["Jun", "Jul"]
    _run(
        deck,
        [
            {
                "op": "format_chart",
                "slide": 3,
                "shape": name,
                "title": "Growth",
                "data_labels": True,
                "number_format": "#,##0",
                "colors": ["#AA3355"],
            }
        ],
    )
    chart = _shape(deck.slides[2], "has_chart").chart
    assert chart.chart_title.text_frame.text == "Growth" and chart.plots[0].has_data_labels
    assert "AA3355" in chart._chartSpace.xml
    _run(deck, [{"op": "change_chart_type", "slide": 3, "shape": name, "kind": "donut"}])
    assert _shape(deck.slides[2], "has_chart").chart.chart_type.name == "DOUGHNUT"
    _valid(deck)


def test_footer_and_slide_numbers(tmp_path: Path) -> None:
    deck = _deck(tmp_path)
    done = _run(deck, [{"op": "set_footer", "text": "Confidential", "slide_numbers": True, "slides": [2, 3]}])
    kinds = {
        p.placeholder_format.type.name: p
        for p in deck.slides[1].placeholders
        if p.placeholder_format.type.name in ("FOOTER", "SLIDE_NUMBER")
    }
    assert kinds["FOOTER"].text_frame.text == "Confidential" and "SLIDE_NUMBER" in kinds
    assert not [p for p in deck.slides[0].placeholders if p.placeholder_format.type.name == "FOOTER"]
    _run(deck, [{"op": "set_footer", "text": "Internal", "slides": [2]}])
    assert kinds["FOOTER"].text_frame.text == "Internal"
    _run(deck, [{"op": "set_footer", "slide_numbers": False}])
    assert not [
        p for s in deck.slides for p in s.placeholders if p.placeholder_format.type.name == "SLIDE_NUMBER"
    ]
    assert done
    _valid(deck)


def test_bulk_notes_delete_shape_and_empty_placeholders(tmp_path: Path) -> None:
    deck = _deck(tmp_path)
    _run(deck, [{"op": "set_notes_bulk", "notes": {"1": "Welcome", "3": "Explain the jump"}}])
    assert deck.slides[0].notes_slide.notes_text_frame.text == "Welcome"
    assert deck.slides[2].notes_slide.notes_text_frame.text == "Explain the jump"
    chart = _shape(deck.slides[2], "has_chart")
    _run(deck, [{"op": "delete_shape", "slide": 3, "shape": chart.shape_id}])
    assert not any(getattr(s, "has_chart", False) for s in deck.slides[2].shapes)
    with pytest.raises(DeckError, match="no shape"):
        _run(deck, [{"op": "delete_shape", "slide": 3, "shape": "text:no such thing"}])
    layout = next(layout for layout in deck.slide_layouts if layout.name == "Title and Content")
    deck.slides.add_slide(layout)
    done = _run(deck, [{"op": "remove_empty_placeholders", "slide": len(deck.slides)}])
    assert "removed 1" in done[0] or "removed 2" in done[0]
    _valid(deck)


def test_replace_text_reaches_chart_titles_series_names_and_alt_text(tmp_path: Path) -> None:
    deck = _deck(tmp_path)
    chart = _shape(deck.slides[2], "has_chart")
    chart.chart.has_title = True
    chart.chart.chart_title.text_frame.text = "FY24 users"
    picture = next(s for s in deck.slides[4].shapes if s.shape_type == 13)
    picture._element.xpath("(.//p:cNvPr)[1]")[0].set("descr", "FY24 dashboard")
    done = _run(deck, [{"op": "replace_text", "find": "FY24", "replace": "FY25"}])
    assert _shape(deck.slides[2], "has_chart").chart.chart_title.text_frame.text == "FY25 users"
    assert picture._element.xpath("(.//p:cNvPr)[1]/@descr")[0] == "FY25 dashboard"
    assert "2 occurrence" in done[0]
    _valid(deck)


# --- add_slide: before the closing slide, and in the look of the deck's own slides (baseline-1/2 finding on d07) ---


def _deck_with_closing(tmp_path: Path) -> Any:
    import json

    from forge.slides.build import build_deck
    from forge.slides.open_deck import open_deck
    from forge.slides.spec import parse_deck

    outline = {
        "title": "Board",
        "slides": [
            {"layout": "title", "title": "Board update"},
            {
                "layout": "bullets",
                "title": "FY24 in numbers",
                "bullets": ["Revenue up", "Margin steady", "Hiring on plan"],
            },
            {"layout": "bullets", "title": "Priorities delivered", "bullets": ["Warehouse", "ERP"]},
            {"layout": "closing", "title": "Thank you"},
        ],
    }
    path = tmp_path / "board.pptx"
    path.write_bytes(build_deck(parse_deck(json.dumps(outline)), lambda name: b"").data)
    return open_deck(path)


def _titles(deck: Any) -> list[str]:
    return [
        next((s.text_frame.text for s in slide.shapes if s.has_text_frame and s.text_frame.text.strip()), "")
        for slide in deck.slides
    ]


def test_a_new_slide_goes_before_the_closing_slide_in_the_decks_own_look(tmp_path: Path) -> None:
    deck = _deck_with_closing(tmp_path)
    _run(
        deck,
        [{"op": "add_slide", "title": "Decisions needed", "body": ["Approve hiring plan", "Approve budget"]}],
    )
    titles = _titles(deck)
    assert titles[-2:] == ["Decisions needed", "Thank you"] and len(titles) == 5
    new = deck.slides[3]
    old = deck.slides[2]
    # same look: same layout, same text boxes at the same places and sizes
    assert new.slide_layout.name == old.slide_layout.name
    assert [(s.left, s.top, s.width) for s in new.shapes if s.has_text_frame] == [
        (s.left, s.top, s.width) for s in old.shapes if s.has_text_frame
    ]
    body = " ".join(s.text_frame.text for s in new.shapes if s.has_text_frame)
    assert "Approve budget" in body and "Priorities delivered" not in body and "Warehouse" not in body
    _valid(deck)


def test_add_slide_with_a_layout_name_also_lands_before_the_closing_slide(tmp_path: Path) -> None:
    deck = _deck_with_closing(tmp_path)
    _run(
        deck, [{"op": "add_slide", "layout": "Title and Content", "title": "Next steps", "body": ["Ship it"]}]
    )
    assert _titles(deck)[-1] == "Thank you"
    assert _titles(deck)[-2] == "Next steps"


def test_an_explicit_position_and_a_chosen_model_slide_are_respected(tmp_path: Path) -> None:
    deck = _deck_with_closing(tmp_path)
    _run(deck, [{"op": "add_slide", "like": 2, "title": "Appendix", "body": ["Detail"], "at": 2}])
    assert _titles(deck)[1] == "Appendix"
    with pytest.raises(DeckError, match="no slide 9"):
        _run(deck, [{"op": "add_slide", "like": 9, "title": "x", "body": ["y"]}])


def test_a_layout_name_on_a_deck_without_placeholder_slides_copies_the_decks_look(tmp_path: Path) -> None:
    deck = _deck_with_closing(tmp_path)
    done = _run(
        deck,
        [
            {
                "op": "add_slide",
                "layout": "Title and Content",
                "title": "Decisions needed",
                "body": ["Approve plan"],
            }
        ],
    )
    assert "added slide 4 of 5" in done[0] and "no move_slide is needed" in done[0]
    new, old = deck.slides[3], deck.slides[2]
    assert [(s.left, s.top, s.width) for s in new.shapes if s.has_text_frame] == [
        (s.left, s.top, s.width) for s in old.shapes if s.has_text_frame
    ]
    _run(
        deck,
        [
            {
                "op": "add_slide",
                "layout": "Title and Content",
                "exact_layout": True,
                "title": "Real layout",
                "body": ["x"],
            }
        ],
    )
    assert any(
        s.is_placeholder for s in deck.slides[3].shapes
    )  # exact_layout forces the layout's own placeholders
