"""D-332, D-333: a template like the company one (infographic samples, charts, a table, misspelt covers, sticky notes) is used as it is."""

from __future__ import annotations

import io
import json

import pytest

pytest.importorskip("pptx")
from pptx import Presentation

from forge.slides.build import build_deck
from forge.slides.edit_find import walk
from forge.slides.spec import parse_deck
from forge.slides.template_samples import analyze_samples
from forge.slides.validate import validate_package
from tests.slide_templates import make_infographic_template


def _build(outline: dict) -> tuple[Presentation, list]:  # type: ignore[type-arg]
    template = make_infographic_template()
    deck = parse_deck(json.dumps({"title": "T", "template": "t.pptx", **outline}))
    built = build_deck(deck, lambda name: template)
    assert not validate_package(built.data), validate_package(built.data)
    return Presentation(io.BytesIO(built.data)), built.slides


def _texts(slide: object) -> list[str]:
    return [
        s.text_frame.text
        for s in walk(slide.shapes)
        if getattr(s, "has_text_frame", False) and s.has_text_frame
    ]  # type: ignore[attr-defined]


def test_samples_are_recognised_by_what_they_hold() -> None:
    samples = analyze_samples(Presentation(io.BytesIO(make_infographic_template())))
    kinds = {s.number: s.kind for s in samples}
    assert kinds[1] == "title" and kinds[2] == "section" and kinds[4] == "chart" and kinds[5] == "chart"
    assert kinds[6] == "table" and kinds[8] == "thanks"
    assert (
        samples[3].chart_families == ["donut"]
        and samples[4].chart_families == ["column"]
        and samples[5].table_sizes == [(4, 3)]
    )


def test_a_deck_built_on_it_uses_the_samples_charts_and_table_and_leaves_no_sticky_note() -> None:
    prs, reports = _build(
        {
            "slides": [
                {"layout": "title", "title": "Quarterly review", "subtitle": "Finance"},
                {"layout": "section", "title": "Results"},
                {
                    "layout": "chart",
                    "title": "Share by region",
                    "kind": "donut",
                    "categories": ["North", "South", "East", "West"],
                    "series": [{"name": "Share", "values": [40, 30, 20, 10]}],
                },
                {
                    "layout": "chart",
                    "title": "Sales by quarter",
                    "kind": "column",
                    "categories": ["Q1", "Q2", "Q3"],
                    "series": [
                        {"name": "2025", "values": [1, 2, 3]},
                        {"name": "2026", "values": [2, 3, 5]},
                        {"name": "Plan", "values": [2, 3, 4]},
                    ],
                },
                {
                    "layout": "table",
                    "title": "Numbers by region",
                    "columns": ["Region", "Revenue", "Margin", "Notes"],
                    "rows": [
                        ["North", 120, "12%", "ok"],
                        ["South", 95, "9%", "low"],
                        ["East", 70, "11%", ""],
                        ["West", 60, "8%", "new"],
                        ["Online", 40, "15%", "up"],
                    ],
                },
                {"layout": "closing", "title": "Thank you"},
            ]
        }
    )
    assert prs.slide_width == (10 * 914400) and len(prs.slides) == 6
    labels = [r.layout for r in reports]
    assert any("template sample 4" in label for label in labels) and any(
        "template sample 5" in label for label in labels
    )
    assert any("template sample 6" in label for label in labels)
    donut = next(
        s for s in walk(prs.slides[2].shapes) if getattr(s, "has_chart", False) and s.has_chart
    ).chart
    assert donut.chart_type.name == "DOUGHNUT" and list(donut.plots[0].categories) == [
        "North",
        "South",
        "East",
        "West",
    ]
    assert list(donut.plots[0].series[0].values) == [40, 30, 20, 10]
    column = next(
        s for s in walk(prs.slides[3].shapes) if getattr(s, "has_chart", False) and s.has_chart
    ).chart
    assert [s.name for s in column.plots[0].series] == ["2025", "2026", "Plan"]
    table = next(s for s in walk(prs.slides[4].shapes) if getattr(s, "has_table", False) and s.has_table)
    assert (len(table.table.rows), len(table.table.columns)) == (6, 4)
    assert (
        table.table.cell(0, 3).text == "Notes"
        and table.table.cell(5, 0).text == "Online"
        and table.table.cell(1, 1).text == "120"
    )
    assert table.width == int(8.4 * 914400)
    for slide in prs.slides:  # nothing of the sticky note, everything of the company's frame
        assert not any("Delete before" in t or "Changing image" in t for t in _texts(slide))
        assert all(shape.name != "Picture 12" for shape in slide.shapes)
    assert all(any(shape.name == "Company logo" for shape in slide.shapes) for slide in list(prs.slides)[:5])
    assert all("Acme confidential" in " ".join(_texts(slide)) for slide in list(prs.slides)[:5])


def test_a_chart_kind_the_template_has_no_sample_for_is_drawn_in_the_template_theme() -> None:
    prs, reports = _build(
        {
            "slides": [
                {"layout": "title", "title": "T"},
                {
                    "layout": "chart",
                    "title": "Trend",
                    "kind": "line",
                    "categories": ["a", "b"],
                    "series": [{"name": "s", "values": [1, 2]}],
                },
            ]
        }
    )
    chart = next(
        s for s in walk(prs.slides[1].shapes) if getattr(s, "has_chart", False) and s.has_chart
    ).chart
    assert "LINE" in chart.chart_type.name and not any(
        "template sample" in r.layout and "chart" in r.layout for r in reports
    )


def test_a_table_with_too_many_rows_falls_back_to_the_quiet_native_table() -> None:
    rows = [[f"R{i}", i] for i in range(20)]
    _, reports = _build(
        {
            "slides": [
                {"layout": "title", "title": "T"},
                {"layout": "table", "title": "Long table", "columns": ["Name", "Value"], "rows": rows},
            ]
        }
    )
    assert not any("table (template sample" in r.layout for r in reports)
