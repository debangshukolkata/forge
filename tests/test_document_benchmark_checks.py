"""D-357: the document benchmark's checks pass on outputs made by DebCraft's own tools and fail on poor ones (no model involved)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("docx")
pytest.importorskip("openpyxl")
pytest.importorskip("pypdf")
pytest.importorskip("reportlab")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "benchmark"))
import run_document_benchmark as bench


def _workspace(tmp_path: Path) -> Path:
    (tmp_path / "project").mkdir()
    return tmp_path


def test_a_good_word_summary_passes_and_an_empty_workspace_fails(tmp_path: Path) -> None:
    from forge.documents.build import build_document
    from forge.documents.spec import parse_document

    assert not bench.check_w01(_workspace(tmp_path))["delivered"]
    outline = {
        "title": "Sales summary",
        "blocks": [
            {"type": "heading", "text": "Summary"},
            {"type": "paragraph", "text": "Total revenue was 734,850, led by West with 294,750."},
            {"type": "heading", "text": "Revenue by region"},
            {
                "type": "table",
                "header": ["Region", "Q1", "Q2"],
                "rows": [
                    ["North", "120400", "133900"],
                    ["South", "98200", "87600"],
                    ["West", "143000", "151750"],
                ],
            },
            {"type": "bullets", "items": ["West grew", "South fell"]},
        ],
    }
    (tmp_path / "project" / "sales-summary.docx").write_bytes(
        build_document(parse_document(json.dumps(outline)), lambda n: b"")
    )
    result = bench.check_w01(tmp_path)
    assert result["checks_failed"] == [], result


def test_a_good_workbook_and_a_pdf_pass(tmp_path: Path) -> None:
    from forge.pdfs.build import build_pdf, parse_pdf_spec
    from forge.sheets.build import build_workbook
    from forge.sheets.spec import parse_workbook

    workspace = _workspace(tmp_path)
    outline = {
        "sheets": [
            {
                "name": "Data",
                "columns": [{"header": "Product"}, {"header": "Amount", "format": "#,##0.00"}],
                "rows": [["Kettle", 1200.5], ["Toaster", -300], ["Blender", 950]],
                "total_row": {"A": "Total", "B": "SUM"},
                "charts": [
                    {
                        "type": "column",
                        "title": "Amount",
                        "data": "B1:B4",
                        "categories": "A2:A4",
                        "anchor": "E2",
                    }
                ],
            }
        ]
    }
    (workspace / "project" / "orders.xlsx").write_bytes(build_workbook(parse_workbook(json.dumps(outline))))
    result = bench.check_w02(workspace)
    assert result["checks_failed"] == [], result
    spec = {
        "title": "Volunteer day",
        "blocks": [
            {
                "type": "paragraph",
                "text": "Saturday 14 June at Riverside Park, meet at the boathouse. Bring gloves.",
            },
            {
                "type": "table",
                "header": ["Time", "What"],
                "rows": [["9:00", "Welcome and safety talk"], ["13:30", "Planting"]],
            },
            {"type": "paragraph", "text": "Maya, 0113 555 0142, volunteers@riverside.example"},
        ],
    }
    (workspace / "project" / "handout.pdf").write_bytes(
        build_pdf(parse_pdf_spec(json.dumps(spec)), lambda n: b"")
    )
    assert bench.check_w03(workspace)["checks_failed"] == []


def test_the_new_checks_fail_on_an_empty_workspace_and_pass_good_outputs(tmp_path: Path) -> None:
    """W5 (D-519): w04 to w07 are proven here without a model: an empty workspace is not delivered, and files built with the tools (or openpyxl) pass."""
    import datetime

    import openpyxl
    from openpyxl.chart import BarChart, Reference
    from openpyxl.worksheet.datavalidation import DataValidation

    from forge.documents.build import build_document
    from forge.documents.spec import parse_document

    workspace = _workspace(tmp_path)
    for check in (bench.check_w04, bench.check_w05, bench.check_w06, bench.check_w07):
        assert not check(workspace)["delivered"]

    proposal = {
        "title": "Website proposal for Harbour Street Bakery",
        "blocks": [
            {"type": "heading", "text": "Summary"},
            {
                "type": "paragraph",
                "text": "A new website with an online order form for Dana Whitfield, live by 18 April.",
            },
            {"type": "heading", "text": "Scope"},
            {
                "type": "bullets",
                "items": ["Discovery workshop", "Design of five pages", "Build and order form"],
            },
            {"type": "heading", "text": "Price"},
            {
                "type": "table",
                "header": ["Phase", "Price"],
                "rows": [
                    ["Discovery", "GBP 1,200"],
                    ["Design", "GBP 2,800"],
                    ["Build", "GBP 3,500"],
                    ["Launch and training", "GBP 900"],
                    ["Total", "GBP 8,400"],
                ],
            },
            {"type": "heading", "text": "Timeline"},
            {"type": "paragraph", "text": "Start 3 March, design approved by 21 March, live by 18 April."},
        ],
    }
    (workspace / "project" / "proposal.docx").write_bytes(
        build_document(parse_document(json.dumps(proposal)), lambda n: b"")
    )
    assert bench.check_w04(workspace)["checks_failed"] == []

    letter = {
        "title": "Place for Anika in the January term",
        "blocks": [
            {"type": "paragraph", "text": "Priya Raman, 14 Elm Court, Millbridge MB3 4QF"},
            {"type": "paragraph", "text": "12 November 2026"},
            {
                "type": "paragraph",
                "text": "The Admissions Office, Harbour Music School, 8 Harbour Street, Millbridge MB1 2AA",
            },
            {
                "type": "paragraph",
                "text": "Dear Admissions Office, my daughter Anika (age 9) has played piano for three years.",
            },
            {
                "type": "paragraph",
                "text": "We can attend a trial lesson on 20 or 27 November. Please write to priya.raman@example.org or 07700 900 456.",
            },
            {"type": "paragraph", "text": "Yours faithfully, Priya Raman"},
        ],
    }
    (workspace / "project" / "letter.docx").write_bytes(
        build_document(parse_document(json.dumps(letter)), lambda n: b"")
    )
    assert bench.check_w05(workspace)["checks_failed"] == []

    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Budget"
    names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sheet.append(["Item", *names])
    sheet.append(["Salary", *[2850] * 12])
    sheet.append(["Rent", *[1050] * 12])
    sheet.append(["Total income", *[f"=SUM({chr(66 + i)}2:{chr(66 + i)}2)" for i in range(12)]])
    sheet.append(["Total expenses", *[f"=SUM({chr(66 + i)}3:{chr(66 + i)}3)" for i in range(12)]])
    sheet.append(["Left", *[f"={chr(66 + i)}4-{chr(66 + i)}5" for i in range(12)]])
    chart = BarChart()
    chart.add_data(Reference(sheet, min_col=2, max_col=13, min_row=6), from_rows=True, titles_from_data=False)
    sheet.add_chart(chart, "B9")
    book.save(workspace / "project" / "budget.xlsx")
    assert bench.check_w06(workspace)["checks_failed"] == []

    tracker = openpyxl.Workbook()
    tasks = tracker.active
    tasks.title = "Tasks"
    tasks.append(["Task", "Owner", "Status", "Due date", "Notes"])
    for number in range(10):
        tasks.append([f"Task {number}", "Sam", "In progress", datetime.date(2026, 12, 1 + number), ""])
    rule = DataValidation(type="list", formula1='"Not started,In progress,Blocked,Done"', allow_blank=False)
    tasks.add_data_validation(rule)
    rule.add("C2:C11")
    tasks.freeze_panes = "A2"
    summary = tracker.create_sheet("Summary")
    for row, status in enumerate(["Not started", "In progress", "Blocked", "Done"], start=1):
        summary.cell(row=row, column=1, value=status)
        summary.cell(row=row, column=2, value=f"=COUNTIF(Tasks!C:C,A{row})")
    tracker.save(workspace / "project" / "tracker.xlsx")
    assert bench.check_w07(workspace)["checks_failed"] == []
