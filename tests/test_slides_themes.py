"""P2.1: 19 themes that are readable, a brand kit that overrides them, and theme suggestions by topic."""

from __future__ import annotations

import json

import pytest

from forge.slides.build import build_deck
from forge.slides.lint import SAFE_FONTS
from forge.slides.spec import SpecError, parse_deck
from forge.slides.themes import (
    THEMES,
    Brand,
    apply_brand,
    contrast,
    contrast_problems,
    mix,
    readable_on,
    suggest_themes,
)


def test_there_are_many_themes_and_each_is_readable() -> None:
    assert len(THEMES) >= 19
    for theme in THEMES.values():
        assert contrast_problems(theme) == [], theme.name
        assert theme.palette[0] == theme.accent and len(theme.palette) == 6
        assert theme.title_font.lower() in SAFE_FONTS and theme.body_font.lower() in SAFE_FONTS


def test_chart_colours_stand_out_from_the_background() -> None:
    for theme in THEMES.values():
        for colour in theme.palette[:5]:
            assert contrast(colour, theme.background) >= 2.9, (theme.name, colour)


def test_themes_are_distinct_not_blue_by_default() -> None:
    accents = {t.accent for t in THEMES.values()}
    assert len(accents) >= 17
    assert sum(1 for t in THEMES.values() if t.dark) >= 4  # dark options exist for keynote style decks


def test_suggestions_follow_the_topic() -> None:
    assert suggest_themes("charity blood donation drive")[0] == "ruby"
    assert "forest" in suggest_themes("sustainability and climate report")
    assert suggest_themes("developer platform engineering")[0] == "graphite"
    assert suggest_themes("zzz qqq") == []


def test_colour_helpers() -> None:
    assert contrast("000000", "FFFFFF") == pytest.approx(21, rel=0.01)
    assert mix("000000", "FFFFFF", 0.5) == "808080"
    assert readable_on("FFFFFF") == "111827" and readable_on("0B1220") == "FFFFFF"


def test_a_brand_kit_overrides_colours_and_fills_in_the_rest_readably() -> None:
    theme, problems = apply_brand(THEMES["clean"], Brand(accent="E4002B", background="FFF4E5"))
    assert theme.accent == "E4002B" and theme.palette[0] == "E4002B" and theme.background == "FFF4E5"
    assert contrast(theme.text, theme.background) >= 4.5 and contrast(theme.muted, theme.background) >= 4.5
    assert contrast(theme.accent_text, theme.accent) >= 4.5
    assert problems == []
    dark, _ = apply_brand(THEMES["clean"], Brand(background="101820"))
    assert dark.dark and contrast(dark.text, dark.background) >= 7


def test_a_brand_with_poor_contrast_is_reported() -> None:
    _, problems = apply_brand(
        THEMES["clean"], Brand(accent="FFE066", background="FFFFFF", accent_text="FFFFFF")
    )
    assert any("accent_text on accent" in p for p in problems) and any(
        "accent on background" in p for p in problems
    )


def _deck(**extra: object) -> object:
    return parse_deck(
        json.dumps({"title": "Deck", "slides": [{"layout": "title", "title": "Q3 review"}], **extra})
    )


def test_the_outline_accepts_any_theme_and_rejects_unknown_ones() -> None:
    assert _deck(theme="forest").theme == "forest"  # type: ignore[attr-defined]
    with pytest.raises(SpecError, match="unknown theme 'neon'"):
        _deck(theme="neon")


def test_a_deck_builds_with_a_brand_kit_and_reports_font_and_contrast_problems() -> None:
    built = build_deck(
        _deck(brand={"accent": "#E4002B", "title_font": "Comic Sans MS", "body_font": "Calibri"}),  # type: ignore[arg-type]
        lambda n: b"",
    )
    assert any("Comic Sans MS" in w and "not on every computer" in w for w in built.deck_warnings)
    bad = build_deck(_deck(brand={"accent": "FFE066", "accent_text": "FFFFFF"}), lambda n: b"")  # type: ignore[arg-type]
    assert any("brand colours" in w for w in bad.deck_warnings)


@pytest.mark.parametrize("name", list(THEMES))
def test_every_theme_builds_a_deck(name: str) -> None:
    deck = parse_deck(
        json.dumps(
            {
                "title": "Deck",
                "theme": name,
                "slides": [
                    {"layout": "title", "title": "Q3 review"},
                    {
                        "layout": "stats",
                        "title": "Weekly users grew 42%",
                        "items": [{"value": "42%", "label": "growth"}],
                    },
                    {
                        "layout": "chart",
                        "title": "Users doubled since January",
                        "categories": ["Jan", "Feb"],
                        "series": [{"name": "Users", "values": [1, 2]}, {"name": "Paid", "values": [1, 1]}],
                    },
                ],
            }
        )
    )
    assert build_deck(deck, lambda n: b"").data[:2] == b"PK"


def test_the_skill_lists_every_theme() -> None:
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "src/forge/skills/make-presentation/SKILL.md").read_text(
        encoding="utf-8"
    )
    for name in THEMES:
        assert f"| `{name}` |" in text, f"theme {name} is missing from the skill table"
    assert '"brand"' in text
