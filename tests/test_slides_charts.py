"""P2.4: charts at full strength: kinds, combination with a second axis, scatter, labels, formats, colours, data files."""

from __future__ import annotations

import io
import json
import re
import zipfile

import pytest

from forge.slides.build import build_deck
from forge.slides.errors import BuildError
from forge.slides.spec import SpecError, parse_deck
from forge.slides.validate import validate_package

CATS = ["Q1", "Q2", "Q3", "Q4"]
BOX = {"x": 1, "y": 2, "w": 6, "h": 4}


def _chart(**options: object) -> dict:  # type: ignore[type-arg]
    return {"type": "chart", **BOX, "categories": CATS, **options}


def _build(element: dict, files: dict[str, bytes] | None = None) -> tuple[bytes, list[str]]:  # type: ignore[type-arg]
    deck = {
        "title": "Deck",
        "slides": [{"layout": "freeform", "title": "Charts tell the numbers fast", "elements": [element]}],
    }
    built = build_deck(parse_deck(json.dumps(deck)), lambda name: (files or {})[name])
    return built.data, [w for s in built.slides for w in s.warnings]


def _xml(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return archive.read("ppt/charts/chart1.xml").decode("utf-8")


def _series(name: str, values: list[float], **extra: object) -> dict:  # type: ignore[type-arg]
    return {"name": name, "values": values, **extra}


@pytest.mark.parametrize(
    ("kind", "tag"),
    [
        ("column", "<c:barChart>"),
        ("bar", "<c:barChart>"),
        ("line", "<c:lineChart>"),
        ("area", "<c:areaChart>"),
        ("stacked_column", 'val="stacked"'),
        ("stacked_bar", 'val="stacked"'),
        ("stacked_area", 'val="stacked"'),
    ],
)
def test_category_chart_kinds(kind: str, tag: str) -> None:
    data, warnings = _build(
        _chart(kind=kind, series=[_series("A", [1, 2, 3, 4]), _series("B", [2, 1, 4, 3])])
    )
    assert tag in _xml(data) and warnings == [] and validate_package(data) == []


def test_pie_and_donut_take_one_series_and_warn_about_many_slices() -> None:
    donut, warnings = _build(_chart(kind="donut", series=[_series("S", [4, 3, 2, 1])]))
    assert "<c:doughnutChart>" in _xml(donut) and warnings == []
    with pytest.raises(BuildError, match="exactly one series"):
        _build(_chart(kind="pie", series=[_series("A", [1, 2, 3, 4]), _series("B", [1, 2, 3, 4])]))
    _, many = _build(_chart(kind="pie", categories=list("abcdefgh"), series=[_series("S", [1] * 8)]))
    assert any("slices" in w for w in many)


def test_a_combination_chart_has_a_line_series_on_a_second_axis() -> None:
    data, warnings = _build(
        _chart(
            kind="column",
            series=[
                _series("Revenue", [10, 12, 14, 16]),
                _series("Margin", [0.2, 0.22, 0.21, 0.25], kind="line", axis="secondary"),
            ],
            y_title="Revenue",
            y2_title="Margin",
            y2_number_format="0%",
        )
    )
    xml = _xml(data)
    assert "<c:barChart>" in xml and "<c:lineChart>" in xml and xml.count("<c:valAx>") == 2
    assert 'val="r"' in xml and "Margin" in xml and 'formatCode="0%"' in xml
    assert warnings == [] and validate_package(data) == []
    assert (
        "invertIfNegative" not in xml[xml.index("<c:lineChart>") :]
    )  # a bar-only element must not leak into a line series


def test_combination_charts_need_columns_and_sensible_series() -> None:
    with pytest.raises(BuildError, match="needs kind 'column'"):
        _build(
            _chart(kind="bar", series=[_series("A", [1, 2, 3, 4]), _series("B", [1, 2, 3, 4], kind="line")])
        )
    with pytest.raises(BuildError, match="second axis is for line series"):
        _build(_chart(kind="column", series=[_series("A", [1, 2, 3, 4], axis="secondary")]))


def test_scatter_needs_points() -> None:
    points = [{"name": "P", "points": [[1, 2], [2, 3], [3, 5]]}]
    data, warnings = _build(
        _chart(kind="scatter", categories=[], series=points, x_title="Spend", y_title="Leads")
    )
    assert "<c:scatterChart>" in _xml(data) and warnings == [] and validate_package(data) == []
    with pytest.raises(BuildError, match="needs `points`"):
        _build(_chart(kind="scatter", categories=[], series=[_series("P", [1, 2])]))


def test_titles_number_formats_colours_and_scale() -> None:
    data, _ = _build(
        _chart(
            kind="column",
            series=[_series("Share", [0.2, 0.5, 0.3, 0.4])],
            title="Share by quarter",
            x_title="Quarter",
            y_title="Share",
            number_format="0%",
            point_colors=["series1", "#C62828", "series3", "series4"],
            y_min=0,
            y_max=1,
            gap_width=60,
        )
    )
    xml = _xml(data)
    assert "Share by quarter" in xml and "Quarter</a:t>" in xml and xml.count('formatCode="0%"') >= 2
    assert (
        'val="C62828"' in xml
        and '<c:min val="0.0"/>' in xml
        and '<c:max val="1.0"/>' in xml
        and 'val="60"' in xml
    )
    assert validate_package(data) == []


def test_legend_and_labels_defaults_and_overrides() -> None:
    labels_on = re.compile(r'<c:showVal val="1"')
    one, _ = _build(_chart(series=[_series("A", [1, 2, 3, 4])]))
    assert "<c:legend>" not in _xml(one) and labels_on.search(_xml(one))  # one series: labels on, no legend
    two, _ = _build(_chart(series=[_series("A", [1, 2, 3, 4]), _series("B", [4, 3, 2, 1])]))
    assert "<c:legend>" in _xml(two) and not labels_on.search(_xml(two))  # two series: legend, no labels
    both = [_series("A", [1, 2, 3, 4]), _series("B", [4, 3, 2, 1])]
    forced, _ = _build(_chart(series=both, data_labels=True, legend="none"))
    assert "<c:legend>" not in _xml(forced) and labels_on.search(_xml(forced))


def test_chart_data_from_a_csv_file() -> None:
    csv = b'Region,Revenue,Cost\nNorth,"1,200",800\nSouth,950,700\nEast,1400,900\n'
    element = {"type": "chart", **BOX, "data_file": "regions.csv"}
    data, warnings = _build(element, {"regions.csv": csv})
    xml = _xml(data)
    assert "North" in xml and "Revenue" in xml and "Cost" in xml and "<c:v>1200.0</c:v>" in xml
    assert warnings == [] and validate_package(data) == []
    with pytest.raises(BuildError, match="needs a header row"):
        _build(dict(element, data_file="bad.csv"), {"bad.csv": b"only one line"})
    with pytest.raises(BuildError, match="no numeric column"):
        _build(dict(element, data_file="words.csv"), {"words.csv": b"A,B\nx,hello\ny,world\n"})


def test_chart_data_from_an_excel_file() -> None:
    openpyxl = pytest.importorskip("openpyxl")
    book = openpyxl.Workbook()
    sheet = book.active
    for row in (["Month", "Users"], ["Jan", 10], ["Feb", 14], ["Mar", 21]):
        sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    element = {"type": "chart", **BOX, "data_file": "users.xlsx", "kind": "line"}
    data, _ = _build(element, {"users.xlsx": buffer.getvalue()})
    assert "Users" in _xml(data) and "<c:v>21.0</c:v>" in _xml(data)


def test_a_chart_without_data_is_an_outline_error() -> None:
    deck = {
        "title": "D",
        "slides": [{"layout": "chart", "title": "Numbers speak for themselves", "kind": "column"}],
    }
    with pytest.raises(SpecError, match="needs `series`"):
        parse_deck(json.dumps(deck))


def test_the_chart_layout_accepts_the_new_options_too() -> None:
    deck = {
        "title": "Deck",
        "slides": [
            {
                "layout": "chart",
                "title": "Revenue grew every quarter",
                "kind": "stacked_column",
                "categories": CATS,
                "series": [_series("A", [1, 2, 3, 4]), _series("B", [2, 1, 4, 3])],
                "number_format": "#,##0",
                "caption": "Source: finance",
            }
        ],
    }
    built = build_deck(parse_deck(json.dumps(deck)), lambda n: b"")
    assert validate_package(built.data) == [] and [w for s in built.slides for w in s.warnings] == []
