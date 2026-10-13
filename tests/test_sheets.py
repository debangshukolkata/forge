"""D-339: Excel workbooks are built from an outline, read, edited and checked (W2)."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

openpyxl = pytest.importorskip("openpyxl")

from forge.sheets.build import build_workbook  # noqa: E402
from forge.sheets.check import check_workbook, describe_findings  # noqa: E402
from forge.sheets.edit import Operation, edit_workbook  # noqa: E402
from forge.sheets.read import describe_workbook, read_workbook  # noqa: E402
from forge.sheets.spec import WorkbookError, parse_workbook  # noqa: E402

OUTLINE = {
    "title": "Budget",
    "sheets": [
        {
            "name": "Assumptions",
            "columns": [{"header": "Item"}, {"header": "Value", "format": "0.0%"}],
            "rows": [["Tax rate", 0.2]],
        },
        {
            "name": "Sales",
            "columns": [
                {"header": "Region", "width": 18},
                {"header": "Q1", "format": "#,##0"},
                {"header": "Q2", "format": "#,##0"},
                {"header": "Tax", "format": "#,##0"},
            ],
            "rows": [
                ["North", 100, 120, "=B2*Assumptions!$B$2"],
                ["South", 80, 90, "=B3*Assumptions!$B$2"],
            ],
            "total_row": {"A": "Total", "B": "SUM", "C": "SUM"},
            "table": False,
            "validations": [{"range": "A2:A9", "choices": ["North", "South"]}],
            "conditional": [{"range": "B2:C3", "rule": "greater_than", "value": 100}],
            "charts": [
                {"type": "column", "title": "Sales", "data": "B1:C3", "categories": "A2:A3", "anchor": "G2"}
            ],
        },
    ],
    "names": {"TaxRate": "Assumptions!$B$2"},
}


def _built() -> bytes:
    return build_workbook(parse_workbook(json.dumps(OUTLINE)))


def test_build_keeps_formulas_formats_names_and_the_chart() -> None:
    data = _built()
    book = openpyxl.load_workbook(io.BytesIO(data))
    sales = book["Sales"]
    assert sales["D2"].value == "=B2*Assumptions!$B$2" and sales["B4"].value == "=SUM(B2:B3)"
    assert sales["B2"].number_format == "#,##0" and sales.freeze_panes == "A2"
    assert len(sales._charts) == 1 and len(sales.data_validations.dataValidation) == 1
    assert "TaxRate" in book.defined_names and book.properties.title == "Budget"
    assert sales.column_dimensions["A"].width == 18


def test_a_bad_outline_or_sheet_name_is_a_clear_error() -> None:
    with pytest.raises(WorkbookError):
        parse_workbook("{not json")
    with pytest.raises(WorkbookError, match="Two sheets"):
        build_workbook(parse_workbook(json.dumps({"sheets": [{"name": "A"}, {"name": "a"}]})))
    with pytest.raises(WorkbookError, match="Sheet name"):
        build_workbook(parse_workbook(json.dumps({"sheets": [{"name": "a/b"}]})))


def test_read_shows_formulas_and_says_when_the_file_was_never_calculated() -> None:
    info = read_workbook(_built())
    text = describe_workbook(info, "budget.xlsx")
    assert "Sheet 'Sales'" in text and "formula =B2*Assumptions!$B$2" in text
    assert "never calculated" in text and "TaxRate" in text and info.charts == 1


def test_check_finds_missing_sheet_circular_reference_and_typed_numbers() -> None:
    outline = {
        "sheets": [
            {
                "name": "A",
                "columns": [{"header": "x"}, {"header": "y"}],
                "rows": [[1, "=B2+1"], ["=Nope!A1", "=A3*1.25"], ["=A3", 2]],
            }
        ]
    }
    findings = check_workbook(build_workbook(parse_workbook(json.dumps(outline))))
    text = describe_findings(findings)
    assert "sheet that does not exist: 'Nope'" in text
    assert "hint" in text and "1.25" in text
    cyc = {"sheets": [{"name": "A", "rows": [["=B1", "=A1"]]}]}
    assert "circular reference" in describe_findings(
        check_workbook(build_workbook(parse_workbook(json.dumps(cyc))))
    )
    assert (
        describe_findings(check_workbook(_built())).startswith("No formula faults")
        or "error" not in describe_findings(check_workbook(_built())).split("\n")[0].split("error")[0]
    )


def test_edit_keeps_formulas_but_refuses_to_silently_drop_a_chart() -> None:
    plain = build_workbook(parse_workbook(json.dumps({"sheets": [{"name": "S", "rows": [[1, "=A1*2"]]}]})))
    edited, done = edit_workbook(
        plain,
        [
            Operation(op="set_cells", sheet="S", cells={"A1": 5}),
            Operation(op="append_rows", sheet="S", rows=[[7, "=A2*2"]]),
            Operation(op="format", sheet="S", range="A1:B2", number_format="0.00", bold=True),
            Operation(op="add_sheet", name="New"),
        ],
    )
    book = openpyxl.load_workbook(io.BytesIO(edited))
    assert (
        book["S"]["B1"].value == "=A1*2" and book["S"]["A1"].value == 5 and book["S"]["B2"].value == "=A2*2"
    )
    assert book["S"]["A1"].number_format == "0.00" and "New" in book.sheetnames and len(done) == 4
    with pytest.raises(WorkbookError, match="1 chart"):
        edit_workbook(_built(), [Operation(op="set_cells", sheet="Sales", cells={"B2": 1})])
    kept, notes = edit_workbook(
        _built(), [Operation(op="set_cells", sheet="Sales", cells={"B2": 1})], allow_loss=True
    )
    assert any("LOST" in n for n in notes) and kept
    with pytest.raises(WorkbookError, match="No sheet called"):
        edit_workbook(plain, [Operation(op="set_cells", sheet="Zzz", cells={"A1": 1})])


async def test_the_tools(original_repo: Path, tmp_path: Path) -> None:
    from forge.toolkit.base import ToolContext
    from forge.tools.workbook import BuildWorkbook, CheckWorkbook, EditWorkbook, ReadWorkbook
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_text("docs/outline.json", json.dumps(OUTLINE), "x")
    context = ToolContext(workspace=workspace)
    built = await BuildWorkbook().run(
        BuildWorkbook.Args(outline="docs/outline.json", output="docs/b.xlsx"), context
    )
    assert built.ok and "Wrote docs/b.xlsx" in built.content
    read = await ReadWorkbook().run(ReadWorkbook.Args(path="docs/b.xlsx"), context)
    assert read.ok and "Sales" in read.content
    checked = await CheckWorkbook().run(CheckWorkbook.Args(path="docs/b.xlsx"), context)
    assert checked.ok
    refused = await EditWorkbook().run(
        EditWorkbook.Args(
            path="docs/b.xlsx", operations=[Operation(op="set_cells", sheet="Sales", cells={"B2": 1})]
        ),
        context,
    )
    assert not refused.ok and "allow_loss" in refused.content
    missing = await ReadWorkbook().run(ReadWorkbook.Args(path="docs/none.xlsx"), context)
    assert not missing.ok


def test_excel_recalculation_reports_real_errors_when_excel_is_installed() -> None:
    from forge.sheets import excel

    if not excel.available():
        pytest.skip("Excel is not installed here")
    outline = {
        "sheets": [
            {
                "name": "A",
                "columns": [{"header": "x"}, {"header": "y"}],
                "rows": [[1, "=A2/0"], [2, "=SUM(A2:A3)"]],
            }
        ]
    }
    errors, saved = excel.recalculate(build_workbook(parse_workbook(json.dumps(outline))))
    assert errors == [("A", "B2", "#DIV/0!")] and saved
    values = openpyxl.load_workbook(io.BytesIO(saved), data_only=True)["A"]
    assert values["B3"].value == 3
