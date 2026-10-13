"""P1.3: row, column and grid containers turn intent into coordinates."""

from __future__ import annotations

import json

import pytest

from forge.slides.build import build_deck
from forge.slides.layout import LayoutError, expand_elements
from forge.slides.spec import SpecError, parse_deck


def text(label: str, **extra: object) -> dict:  # type: ignore[type-arg]
    return {"type": "text", "text": label, **extra}


def expand(node: dict) -> list[dict]:  # type: ignore[type-arg]
    return expand_elements([node], 1)


def test_a_row_of_three_equal_cards_with_a_gap() -> None:
    cards = expand(
        {
            "type": "row",
            "x": 0.7,
            "y": 2,
            "w": 12,
            "h": 3,
            "gap": 0.4,
            "children": [text("a"), text("b"), text("c")],
        }
    )
    widths = [c["w"] for c in cards]
    assert widths == [3.733] * 3
    assert [c["x"] for c in cards] == [0.7, 4.833, 8.967]
    assert all(c["y"] == 2 and c["h"] == 3 for c in cards)  # children fill the cross axis


def test_weights_and_fixed_sizes_share_the_space() -> None:
    cards = expand(
        {
            "type": "row",
            "x": 0,
            "y": 0,
            "w": 10,
            "h": 2,
            "gap": 0,
            "children": [text("a", length=2), text("b", weight=1), text("c", weight=3)],
        }
    )
    assert [c["w"] for c in cards] == [2, 2, 6]
    assert all("weight" not in c and "size" not in c for c in cards)


def test_a_column_stacks_downwards_and_cross_alignment_centres_a_fixed_width() -> None:
    items = expand(
        {
            "type": "column",
            "x": 1,
            "y": 1,
            "w": 6,
            "h": 5,
            "gap": 0.5,
            "align": "center",
            "children": [text("a", cross=2), text("b")],
        }
    )
    assert items[0]["x"] == 3 and items[0]["w"] == 2  # centred in the 6 in column
    assert items[1]["x"] == 1 and items[1]["w"] == 6  # no cross size: fills the width
    assert items[0]["y"] == 1 and items[1]["y"] == pytest.approx(1 + items[0]["h"] + 0.5)
    assert items[0]["h"] == items[1]["h"] == 2.25


def test_a_grid_fills_rows_and_supports_colspan() -> None:
    cells = expand(
        {
            "type": "grid",
            "x": 0,
            "y": 0,
            "w": 9,
            "h": 5,
            "cols": 3,
            "gap": 0.5,
            "children": [text("1"), text("2"), text("3"), text("4", colspan=2), text("5")],
        }
    )
    assert [(c["x"], c["y"]) for c in cells] == [(0, 0), (3.167, 0), (6.333, 0), (0, 2.75), (6.333, 2.75)]
    assert cells[3]["w"] == 5.833 and cells[0]["w"] == 2.667 and cells[0]["h"] == 2.25


def test_containers_nest() -> None:
    cells = expand(
        {
            "type": "row",
            "x": 0,
            "y": 0,
            "w": 10,
            "h": 4,
            "gap": 0,
            "children": [
                text("left"),
                {"type": "column", "gap": 0, "children": [text("top"), text("bottom")]},
            ],
        }
    )
    assert [(c["x"], c["y"], c["w"], c["h"]) for c in cells] == [(0, 0, 5, 4), (5, 0, 5, 2), (5, 2, 5, 2)]


@pytest.mark.parametrize(
    ("node", "message"),
    [
        ({"type": "row", "x": 0, "y": 0, "w": 5, "children": [text("a")]}, "needs x, y, w and h"),
        ({"type": "row", "x": 0, "y": 0, "w": 5, "h": 2, "children": []}, "non-empty 'children'"),
        (
            {
                "type": "row",
                "x": 0,
                "y": 0,
                "w": 5,
                "h": 2,
                "gap": 1,
                "children": [text("a", length=3), text("b", length=3)],
            },
            "fixed width",
        ),
        (
            {"type": "grid", "x": 0, "y": 0, "w": 5, "h": 2, "cols": 2, "children": [text("a", colspan=3)]},
            "colspan",
        ),
        ({"type": "row", "x": 0, "y": 0, "w": 5, "h": 2, "align": "left", "children": [text("a")]}, "align"),
        ({"type": "row", "x": 0, "y": 0, "w": 5, "h": 2, "pad": 3, "children": [text("a")]}, "no room"),
        ({"type": "row", "x": 0, "y": 0, "w": 5, "h": 2, "children": [text("a", cross=9)]}, "across"),
    ],
)
def test_mistakes_are_reported_in_words(node: dict, message: str) -> None:  # type: ignore[type-arg]
    with pytest.raises(LayoutError, match=message):
        expand(node)


def test_a_freeform_slide_with_a_row_builds_without_warnings() -> None:
    card = {
        "type": "text",
        "text": "Fast\nSearch is four times faster",
        "size": 20,
        "fill": "surface",
        "rounded": True,
    }
    deck = {
        "title": "Deck",
        "slides": [
            {
                "layout": "freeform",
                "title": "Three reasons to switch this quarter",
                "elements": [
                    {
                        "type": "row",
                        "x": 0.7,
                        "y": 2.2,
                        "w": 11.9,
                        "h": 3.2,
                        "gap": 0.4,
                        "children": [dict(card), dict(card), dict(card)],
                    }
                ],
            }
        ],
    }
    built = build_deck(parse_deck(json.dumps(deck)), lambda n: b"")
    assert [w for s in built.slides for w in s.warnings] == []


def test_a_layout_mistake_reaches_the_model_as_a_spec_error() -> None:
    deck = {
        "title": "Deck",
        "slides": [
            {
                "layout": "freeform",
                "title": "x",
                "elements": [{"type": "row", "x": 0, "y": 0, "w": 5, "h": 2, "children": []}],
            }
        ],
    }
    with pytest.raises(SpecError, match=r"slide 1, element 1 \(row\)"):
        parse_deck(json.dumps(deck))
