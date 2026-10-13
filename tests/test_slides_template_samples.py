"""Sample slides of a corporate template: described by slots, filled with new content, no sample wording left (P2.21)."""

from __future__ import annotations

import io

import pytest

pytest.importorskip("pptx")
from pptx import Presentation  # noqa: E402

from forge.slides.edit_find import walk  # noqa: E402
from forge.slides.template_samples import analyze_samples, describe_samples, fill_sample  # noqa: E402
from tests.slide_templates import make_corporate_template  # noqa: E402


def _template() -> tuple[Presentation, list]:
    prs = Presentation(io.BytesIO(make_corporate_template()))
    return prs, analyze_samples(prs)


def _texts(slide: object) -> list[str]:
    return [
        s.text_frame.text
        for s in walk(slide.shapes)
        if getattr(s, "has_text_frame", False) and s.has_text_frame
    ]  # type: ignore[attr-defined]


def test_samples_are_classified_by_what_they_hold() -> None:
    _, samples = _template()
    assert [s.kind for s in samples] == ["title", "cards", "stats", "bullets", "thanks"]
    assert len(samples[1].items) == 3 and set(samples[1].items[0].parts) == {"heading", "text"}
    assert set(samples[2].items[0].parts) == {"number", "heading", "text"}


def test_company_text_repeated_on_every_sample_is_fixed() -> None:
    _, samples = _template()
    fixed = [slot.text for sample in samples for slot in sample.slots if slot.fixed]
    assert fixed and set(fixed) == {"Acme Corp. Confidential"}


def test_description_lists_slots_and_items_for_the_model() -> None:
    _, samples = _template()
    text = describe_samples(samples)
    assert "Slide 2 [cards]" in text and "items: 3 groups, each with heading/text" in text
    assert "Confidential" not in text  # fixed text is not offered as a slot


def test_filling_cards_replaces_text_and_keeps_the_company_line() -> None:
    prs, samples = _template()
    slide = prs.slides[1]
    problems = fill_sample(
        slide,
        samples[1],
        {
            "title": "Why customers stay",
            "items": [
                {"heading": "Speed", "text": "Answers in minutes."},
                {"heading": "Care", "text": "A named contact."},
                {"heading": "Value", "text": "No hidden fees."},
            ],
        },
    )
    texts = _texts(slide)
    assert not problems
    assert "Why customers stay" in texts and "Speed" in texts and "No hidden fees." in texts
    assert "Acme Corp. Confidential" in texts
    assert not [t for t in texts if "Pillar" in t or "sample" in t.lower()]


def test_fewer_items_than_groups_removes_the_spare_cards_and_their_backgrounds() -> None:
    prs, samples = _template()
    slide = prs.slides[1]
    before = len(slide.shapes)
    fill_sample(slide, samples[1], {"title": "Two things", "items": ["Speed", "Care"]})
    texts = _texts(slide)
    assert "Speed" in texts and "Care" in texts and not [t for t in texts if "Pillar" in t]
    assert len(slide.shapes) <= before - 3  # the third card's heading, text and background are gone


def test_too_many_items_and_unknown_slots_are_reported() -> None:
    prs, samples = _template()
    problems = fill_sample(prs.slides[1], samples[1], {"items": ["a", "b", "c", "d"], "picture": "x.png"})
    assert any("4 items" in p for p in problems) and any("no 'picture'" in p for p in problems)


def test_unreplaced_sample_words_are_removed() -> None:
    prs, samples = _template()
    slide = prs.slides[0]
    fill_sample(slide, samples[0], {"title": "Q3 review"})  # no subtitle given
    texts = _texts(slide)
    assert "Q3 review" in texts and not [t for t in texts if "subtitle" in t.lower()]


def test_bullets_fill_the_body_with_one_paragraph_per_line() -> None:
    prs, samples = _template()
    slide = prs.slides[3]
    fill_sample(slide, samples[3], {"title": "Plan", "body": ["One", "Two", "Three", "Four"]})
    body = next(s for s in slide.placeholders if s.placeholder_format.idx == 1)
    assert [p.text for p in body.text_frame.paragraphs] == ["One", "Two", "Three", "Four"]
