"""D-355: a messy CSV or sheet becomes a clean workbook, and every change and doubt is reported."""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from forge.sheets.clean import clean_table, read_rows  # noqa: E402

MESSY = (
    b"Quarterly sales export;;;;\n"
    b"Generated 03/01/2026;;;;\n"
    b";;;;\n"
    b"Region;Order date;Revenue;Margin;Notes\n"
    b'North ;15/01/2026;"$1,200.50";12%;ok\n'
    b"South;16/01/2026;(300);8%;N/A\n"
    b";;;;\n"
    b'North ;15/01/2026;"$1,200.50";12%;ok\n'
    b'West;28/02/2026;"$950";-;late\n'
    b'Total;;"$1,850.50";;\n'
)


def test_title_lines_blank_rows_duplicates_numbers_and_dates_are_cleaned_and_reported() -> None:
    result = clean_table(read_rows(MESSY, "export.csv"))
    names = [c["header"] for c in result.columns]
    assert names == ["Region", "Order date", "Revenue", "Margin", "Notes"]
    rows = result.rows
    assert rows[0] == ["North", "2026-01-15", 1200.5, 0.12, "ok"]
    assert rows[1][2] == -300 and rows[1][4] is None  # (300) is negative, N/A is empty
    assert rows[2][0] == "West" and rows[2][3] is None  # "-" is empty
    assert len(rows) == 4  # the duplicate North row and the blank rows are gone; the total line stays
    formats = {c["header"]: c.get("format") for c in result.columns}
    assert (
        formats["Order date"] == "yyyy-mm-dd"
        and formats["Margin"] == "0.0%"
        and "$" in (formats["Revenue"] or "")
    )
    text = " ".join(result.report)
    assert (
        "title line(s)" in text
        and "duplicate row" in text
        and "blank row" in text
        and "day first" in text
        and "look like totals" in text
    )
    assert "GUESS" not in text  # 28/02 settles day-first


def test_an_ambiguous_date_column_is_a_stated_guess() -> None:
    result = clean_table([["Day", "Value"], ["01/02/2026", "5"], ["03/04/2026", "6"]])
    assert any("GUESS" in line for line in result.report) and result.rows[0][0] == "2026-02-01"
    month_first = clean_table([["Day", "Value"], ["01/22/2026", "5"], ["03/04/2026", "6"]])
    assert month_first.rows[0][0] == "2026-01-22" and not any("GUESS" in line for line in month_first.report)


def test_a_header_over_two_rows_and_empty_columns_are_handled() -> None:
    rows = [
        ["Report", "", "", ""],
        ["Area", "Population", "", ""],
        ["", "2022", "2023", ""],
        ["North", "1,000", "1,100", ""],
        ["South", "2,000", "2,100", ""],
    ]
    result = clean_table(rows)
    assert [c["header"] for c in result.columns] == ["Area", "Population 2022", "Population 2023"]
    assert (
        result.rows[0] == ["North", 1000, 1100] and any("2 rows" in line for line in result.report)
    ) or any("header spread" in line for line in result.report)


def test_clean_data_is_left_alone_and_the_report_says_so() -> None:
    result = clean_table([["A", "B"], ["x", 1], ["y", 2]])
    assert result.rows == [["x", 1], ["y", 2]] and result.report == ["the table was already clean"]


def test_an_excel_sheet_with_real_dates_keeps_them() -> None:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["When", "What"])
    sheet.append([date(2026, 1, 5), "a"])
    sheet.append([date(2026, 1, 6), "b"])
    out = io.BytesIO()
    book.save(out)
    result = clean_table(read_rows(out.getvalue(), "x.xlsx"))
    assert result.rows[0][0] == "2026-01-05" and result.columns[0]["format"] == "yyyy-mm-dd"


async def test_the_tool_writes_a_workbook_with_real_dates_numbers_and_a_report(
    original_repo: Path, tmp_path: Path
) -> None:
    from forge.toolkit.base import ToolContext
    from forge.tools.workbook import CleanTable
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_bytes("data/export.csv", MESSY, "x")
    context = ToolContext(workspace=workspace)
    done = await CleanTable().run(
        CleanTable.Args(path="data/export.csv", output="data/clean.xlsx", outline_output="data/clean.json"),
        context,
    )
    assert done.ok and "What was changed" in done.content and "duplicate row" in done.content
    book = openpyxl.load_workbook(io.BytesIO(workspace.path_of("data/clean.xlsx").read_bytes()))
    sheet = book["Data"]
    assert (sheet["A1"].value == "Region" and isinstance(sheet["B2"].value, (date,))) or hasattr(
        sheet["B2"].value, "year"
    )
    assert sheet["C2"].value == 1200.5 and sheet["D2"].number_format == "0.0%" and sheet.freeze_panes == "A2"
    assert workspace.path_of("data/clean.json").is_file()
    bad = await CleanTable().run(CleanTable.Args(path="data/export.csv", output="data/clean.csv"), context)
    assert not bad.ok
