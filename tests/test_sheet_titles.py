"""D-543: a sheet title above the table; the outline's addresses are written as if the header were row 1 and the builder moves them."""

from __future__ import annotations

import io
import json

import pytest

openpyxl = pytest.importorskip("openpyxl")

from forge.sheets.build import build_workbook  # noqa: E402
from forge.sheets.check import check_workbook  # noqa: E402
from forge.sheets.spec import parse_workbook  # noqa: E402
from forge.sheets.titles import shift_formula  # noqa: E402

OUTLINE = {
    "sheets": [
        {
            "name": "Sales",
            "title": "Sales by month",
            "subtitle": "January to March 2026, in GBP",
            "columns": [{"header": "Month"}, {"header": "Revenue", "format": "#,##0"}, {"header": "Share"}],
            "rows": [
                ["Jan", 100, "=B2/SUM($B$2:$B$4)"],
                ["Feb", 150, "=B3/SUM($B$2:$B$4)"],
                ["Mar", 250, "=B4/SUM($B$2:$B$4)"],
            ],
            "table": True,
            "total_row": {"A": "Total", "B": "SUM"},
            "validations": [{"range": "B2:B4", "whole": [0, 100000]}],
            "conditional": [{"range": "B2:B4", "rule": "greater_than", "value": 200}],
            "charts": [{"type": "column", "data": "B1:B4", "categories": "A2:A4", "anchor": "E2"}],
            "notes": {"B1": "Source: the till export"},
        },
        {
            "name": "Summary",
            "columns": [{"header": "Measure"}, {"header": "Value"}],
            "rows": [
                ["Best month", "=INDEX(Sales!A2:A4, MATCH(MAX(Sales!$B$2:$B$4), Sales!B2:B4, 0))"],
                ["Rate", "=TaxRate"],
                ["Label", '="See A1"'],
            ],
        },
    ],
    "names": {"TaxRate": "Sales!$B$2"},
}


def _book() -> object:
    return openpyxl.load_workbook(io.BytesIO(build_workbook(parse_workbook(json.dumps(OUTLINE)))))


def test_a_titled_sheet_starts_its_table_below_the_title_and_every_address_moves_with_it() -> None:
    book = _book()
    sales = book["Sales"]
    assert sales["A1"].value == "Sales by month" and sales["A1"].font.bold and sales["A1"].font.size == 16
    assert sales["A2"].value == "January to March 2026, in GBP" and sales["A3"].value is None
    assert sales["A4"].value == "Month" and sales["A5"].value == "Jan"
    assert sales["C5"].value == "=B5/SUM($B$5:$B$7)"  # absolute addresses move too: the whole table moved
    assert sales["B8"].value == "=SUM(B5:B7)" and sales["A8"].value == "Total"
    assert sales.tables[next(iter(sales.tables))].ref == "A4:C7"
    assert sales.freeze_panes == "A5" and sales.print_title_rows == "$4:$4"
    assert str(sales.data_validations.dataValidation[0].sqref) == "B5:B7"
    assert [str(rule.sqref) for rule in sales.conditional_formatting] == ["B5:B7"]
    assert sales["B4"].comment is not None and sales["B1"].comment is None
    reference = sales._charts[0].series[0].val.numRef.f
    assert reference.endswith("$B$5:$B$7"), reference


def test_other_sheets_and_names_follow_a_titled_sheet_and_untitled_sheets_stay() -> None:
    book = _book()
    summary = book["Summary"]
    assert summary["A1"].value == "Measure"  # no title: nothing moves on this sheet
    assert summary["B2"].value == "=INDEX(Sales!A5:A7, MATCH(MAX(Sales!$B$5:$B$7), Sales!B5:B7, 0))"
    assert summary["B3"].value == "=TaxRate" and summary["B4"].value == '="See A1"'
    assert book.defined_names["TaxRate"].attr_text == "Sales!$B$5"


def test_the_titled_workbook_passes_its_own_check() -> None:
    data = build_workbook(parse_workbook(json.dumps(OUTLINE)))
    assert not [finding for finding in check_workbook(data) if "error" in str(finding).lower()]


def test_the_formula_shifter_leaves_names_text_and_whole_columns_alone() -> None:
    moved = {"Plan": 3, "My sheet": 3}
    assert shift_formula("=SUM(A:A)+COUNT(2:3)", moved, "Plan") == "=SUM(A:A)+COUNT(5:6)"
    assert shift_formula("='My sheet'!C2*Other!C2", moved, "Plan") == "='My sheet'!C5*Other!C2"
    assert shift_formula('=IF(B2>0,"B2 ok",Rate2025)', moved, "Plan") == '=IF(B5>0,"B2 ok",Rate2025)'


def test_the_build_result_says_where_titled_tables_landed_and_names_untitled_sheets() -> None:
    from forge.tools.workbook import _title_lines

    lines = _title_lines(parse_workbook(json.dumps(OUTLINE)))
    assert "Titled: Sales: title in row 1, header in row 4, data from row 5" in lines
    assert "No title: Summary." in lines


def test_a_sheet_with_charts_a_little_over_one_page_is_fitted_on_one_and_a_long_table_is_not() -> None:
    """D-543, doc-5 w14: three title rows pushed a chart across the page break; page 2 held a strip of it under the repeated header."""
    months = [[f"2026-{month:02d}", 1000 + month] for month in range(1, 7)]
    charts = [
        {"type": "column", "data": "B1:B7", "categories": "A2:A7", "anchor": "E5"},
        {"type": "line", "data": "B1:B7", "categories": "A2:A7", "anchor": "E25"},
    ]
    dashboard = {
        "name": "D",
        "title": "KPIs",
        "columns": [{"header": "Month"}, {"header": "Value"}],
        "rows": months,
        "charts": charts,
    }
    long_table = {"name": "L", "columns": [{"header": "Row"}], "rows": [[n] for n in range(200)]}
    book = openpyxl.load_workbook(
        io.BytesIO(build_workbook(parse_workbook(json.dumps({"sheets": [dashboard, long_table]}))))
    )
    assert book["D"].page_setup.fitToHeight == 1
    assert book["L"].page_setup.fitToHeight == 0  # many pages of table stay readable, one page wide
