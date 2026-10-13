"""P1.5 to P1.7: the design lint (topic titles, repeated layouts, text-only decks, accent bars, unsafe fonts)."""

from __future__ import annotations

import json

from forge.slides.build import build_deck
from forge.slides.lint import deck_warnings, font_warning, title_warning
from forge.slides.spec import parse_deck
from forge.slides.themes import THEMES


def _deck(slides: list[dict]) -> object:  # type: ignore[type-arg]
    return parse_deck(json.dumps({"title": "Deck", "slides": slides}))


def _bullets(title: str) -> dict:  # type: ignore[type-arg]
    return {"layout": "bullets", "title": title, "bullets": ["one", "two"]}


def test_topic_titles_are_flagged_and_takeaways_are_not() -> None:
    assert title_warning("Search") and "topic" in title_warning("Search")  # type: ignore[operator]
    assert title_warning("Q3 results") is None or "topic" in (title_warning("Q3 results") or "")
    assert title_warning("Search is now 4x faster") is None
    assert title_warning("Revenue 42%") is None  # a figure carries a message
    long = " ".join(["word"] * 14)
    assert "14 words" in (title_warning(long) or "")


def test_fonts_every_office_has_pass_and_others_are_flagged() -> None:
    for name in ("Calibri", "arial", "Times New Roman", "Courier New", "Georgia"):
        assert font_warning(name) is None
    assert "not on every computer" in (font_warning("Segoe UI") or "")
    assert all(
        font_warning(t.title_font) is None and font_warning(t.body_font) is None for t in THEMES.values()
    )


def test_a_run_of_the_same_layout_and_a_wall_of_bullets_are_reported() -> None:
    deck = _deck([_bullets(f"Point number {i} is clear") for i in range(5)])
    text = " | ".join(deck_warnings(deck))  # type: ignore[arg-type]
    assert "'bullets' layout 3 or more times in a row" in text
    assert "5 of 5 content slides are text only" in text


def test_a_varied_deck_with_visuals_has_no_deck_warnings() -> None:
    deck = _deck(
        [
            {"layout": "title", "title": "Q3 review"},
            _bullets("We shipped three things"),
            {
                "layout": "stats",
                "title": "Weekly users grew 42%",
                "items": [{"value": "42%", "label": "growth"}],
            },
            {
                "layout": "chart",
                "title": "Users doubled since January",
                "categories": ["Jan", "Feb"],
                "series": [{"name": "Users", "values": [1, 2]}],
            },
            {"layout": "quote", "quote": "Simple is hard, and worth it."},
            _bullets("Two risks need a decision"),
        ]
    )
    assert deck_warnings(deck) == []  # type: ignore[arg-type]


def test_an_accent_bar_under_a_freeform_title_is_reported() -> None:
    bar = {"type": "shape", "shape": "rect", "x": 0.7, "y": 1.7, "w": 1.0, "h": 0.06}
    deck = _deck([{"layout": "freeform", "title": "One idea per slide wins", "elements": [bar]}])
    assert "accent bar" in " ".join(deck_warnings(deck))  # type: ignore[arg-type]


def test_the_builder_no_longer_draws_an_accent_bar_and_reports_lint() -> None:
    built = build_deck(_deck([_bullets("Search"), _bullets("x"), _bullets("y")]), lambda n: b"")  # type: ignore[arg-type]
    assert any("topic" in w for w in built.slides[0].warnings)
    assert any("layout 3 or more times" in w for w in built.deck_warnings)


def test_three_plain_bullet_slides_in_a_row_are_flagged() -> None:
    deck = _deck(
        [
            _bullets("First point made here"),
            _bullets("Second point made here"),
            _bullets("Third point made here"),
        ]
    )
    assert "plain bullet lists" in " | ".join(deck_warnings(deck))  # type: ignore[arg-type]


def test_a_deck_with_too_many_slides_for_its_minutes_is_flagged() -> None:
    slides = [
        {
            "layout": "stats",
            "title": f"Number {i} tells the story",
            "items": [{"value": str(i), "label": "x"}],
        }
        for i in range(12)
    ]
    long = _deck(slides)
    long.minutes = 20  # type: ignore[attr-defined]
    assert "too many for 20 minutes" in " | ".join(deck_warnings(long))  # type: ignore[arg-type]
    long.minutes = 45  # type: ignore[attr-defined]
    assert not [w for w in deck_warnings(long) if "minutes" in w]  # type: ignore[arg-type]
