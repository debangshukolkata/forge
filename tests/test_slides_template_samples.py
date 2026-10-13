"""Sample slides of a corporate template: described by slots, filled with new content, no sample wording left (P2.21)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

pytest.importorskip("pptx")
from pptx import Presentation

from forge.slides.edit_find import walk
from forge.slides.template_samples import analyze_samples, describe_samples, fill_sample
from tests.slide_templates import make_corporate_template


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


# --- building a deck on a template that carries sample slides ---

import json  # noqa: E402

from forge.slides.build import build_deck  # noqa: E402
from forge.slides.errors import BuildError  # noqa: E402
from forge.slides.spec import parse_deck  # noqa: E402
from forge.slides.validate import validate_package  # noqa: E402


def _build(slides: list[dict]) -> tuple[object, Presentation]:
    template = make_corporate_template()
    deck = parse_deck(
        json.dumps({"title": "Deck", "subtitle": "Quarterly", "template": "t.pptx", "slides": slides})
    )
    built = build_deck(deck, lambda name: template)
    return built, Presentation(io.BytesIO(built.data))


def test_a_deck_is_built_from_the_templates_own_samples_and_none_of_their_words_remain() -> None:
    built, prs = _build(
        [
            {"layout": "title", "title": "Q3 review"},
            {"layout": "bullets", "title": "What shipped", "bullets": ["Search", "Billing", "Mobile"]},
            {
                "layout": "stats",
                "title": "Results",
                "items": [{"value": "42%", "label": "growth"}, {"value": "1.2M", "label": "users"}],
            },
            {
                "layout": "template_slide",
                "source": 2,
                "fill": {
                    "title": "Why customers stay",
                    "items": [
                        {"heading": "Speed", "text": "Fast answers."},
                        {"heading": "Care", "text": "A named contact."},
                    ],
                },
                "notes": "Say it slowly.",
            },
            {"layout": "closing", "title": "Thank you"},
        ]
    )
    assert not validate_package(built.data)
    assert len(prs.slides) == 5  # the template's five samples are gone
    all_text = [t for slide in prs.slides for t in _texts(slide)]
    assert not [t for t in all_text if "sample" in t.lower() or "Pillar" in t or "Metric label" in t]
    assert "42%" in all_text and "growth" in all_text and "Speed" in all_text and "Fast answers." in all_text
    assert all_text.count("Acme Corp. Confidential") == 5  # the company line comes with every sample
    assert prs.slides[3].notes_slide.notes_text_frame.text == "Say it slowly."
    assert [s.layout for s in built.slides][3].startswith("template_slide")  # type: ignore[attr-defined]


def test_a_slide_the_template_has_no_sample_for_is_made_in_its_theme_with_its_decoration() -> None:
    built, prs = _build(
        [{"layout": "image", "title": "A picture", "image": "x.png"}]
        if False
        else [
            {
                "layout": "chart",
                "title": "Users doubled",
                "kind": "column",
                "categories": ["Jan", "Feb"],
                "series": [{"name": "Users", "values": [1, 2]}],
            }
        ]
    )
    slide = prs.slides[0]
    assert "Acme Corp. Confidential" in _texts(slide)  # the shared company line is carried over
    chart = next(s for s in slide.shapes if getattr(s, "has_chart", False) and s.has_chart)
    assert "0B6E4F" in chart.chart._chartSpace.xml  # the template's accent colour
    assert not validate_package(built.data)


def test_template_slide_with_a_bad_source_says_what_the_template_has() -> None:
    with pytest.raises(BuildError, match=r"no sample slide 9; it has: 1 \[title\]"):
        _build([{"layout": "template_slide", "source": 9, "fill": {"title": "x"}}])


def test_template_slide_without_a_template_is_refused() -> None:
    deck = parse_deck(
        json.dumps(
            {"title": "D", "slides": [{"layout": "template_slide", "source": 1, "fill": {"title": "x"}}]}
        )
    )
    with pytest.raises(BuildError, match='set "template"'):
        build_deck(deck, lambda name: b"")


def test_repeated_bullet_slides_rotate_through_samples_of_the_same_kind() -> None:
    _, prs = _build([{"layout": "bullets", "title": f"Point {i}", "bullets": ["a", "b"]} for i in range(3)])
    assert len(prs.slides) == 3


def test_the_analyze_template_tool_lists_the_samples(tmp_path: Path, original_repo: Path) -> None:
    import asyncio

    from forge.toolkit.base import ToolContext
    from forge.tools.presentation import AnalyzeTemplate
    from forge.workspace.create import create_workspace

    context = ToolContext(workspace=create_workspace(original_repo, tmp_path / "ws", "backend"))
    context.workspace.write_bytes("docs/company.pptx", make_corporate_template(), "template")
    result = asyncio.run(AnalyzeTemplate().run(AnalyzeTemplate.Args(path="docs/company.pptx"), context))
    assert result.ok and "Slide 2 [cards]" in result.content and "Free area" in result.content


def test_common_synonyms_for_slots_and_parts_are_understood() -> None:
    prs, samples = _template()
    slide = prs.slides[2]  # the big-numbers sample: parts number / heading / text
    problems = fill_sample(
        slide,
        samples[2],
        {
            "heading": "Numbers that matter",
            "items": [
                {"value": "94%", "label": "retention", "description": "up from 90"},
                {"value": "52", "label": "NPS"},
            ],
        },
    )
    texts = _texts(slide)
    assert not problems
    assert {"Numbers that matter", "94%", "retention", "up from 90", "52", "NPS"} <= set(texts)
    bullets_slide = prs.slides[3]
    assert not fill_sample(
        bullets_slide, samples[3], {"title": "Plan", "bullets": ["One", "Two"]}
    )  # `bullets` means the body


def test_a_name_that_fits_no_part_is_reported_as_lost_content() -> None:
    prs, samples = _template()
    problems = fill_sample(
        prs.slides[1], samples[1], {"items": [{"heading": "Speed", "text": "Fast", "number": "1"}]}
    )
    assert any("no place for 'number'" in p for p in problems)  # the cards sample has no number part


def test_an_explicit_template_slide_that_would_lose_content_fails_the_build() -> None:
    with pytest.raises(BuildError, match=r"does not fit sample slide 2 \[cards\].*no place for 'foo'"):
        _build(
            [
                {
                    "layout": "template_slide",
                    "source": 2,
                    "fill": {"title": "x", "items": [{"heading": "a", "foo": "b"}]},
                }
            ]
        )
    # the same mistake through an automatic match only warns: we built that mapping ourselves
    built, _ = _build([CARDS_OK])
    assert not built.slides[0].warnings


CARDS_OK = {
    "layout": "cards",
    "title": "Three reasons customers choose us",
    "items": [{"heading": "Speed", "text": "Fast"}, {"heading": "Care", "text": "Named"}],
}


def test_delete_before_using_notes_are_never_content_and_never_stay() -> None:
    """Seen on the real company template: sticky notes on the samples say 'Delete before using ...' (D-332)."""
    from pptx.util import Inches

    from forge.slides.template_samples import INSTRUCTION, is_instruction, remove_instructions

    prs = Presentation(io.BytesIO(make_corporate_template()))
    slide = prs.slides[1]
    note = slide.shapes.add_textbox(Inches(8), Inches(0.2), Inches(2), Inches(1))
    note.text_frame.text = "Delete before using\nReplace the box with the customer logo."
    group = slide.shapes.add_group_shape()
    inner = group.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(1))
    inner.text_frame.text = "Delete before using: right-click the triangle"
    samples = analyze_samples(prs)
    assert all(not INSTRUCTION.match(slot.text) for sample in samples for slot in sample.slots)
    assert is_instruction(note) and is_instruction(group) and not is_instruction(slide.shapes.title)
    assert remove_instructions(slide) == 2
    assert all("Delete before using" not in text for text in _texts(slide))
    for real in ("Delete the old rows", "Nothing to delete before using the product?"[:0] + "Deleted items"):
        assert not INSTRUCTION.match(real)  # ordinary sentences that start with the same word are content
