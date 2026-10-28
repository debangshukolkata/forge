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


def test_the_edit_and_extract_checks_fail_on_an_empty_workspace_and_pass_good_outputs(tmp_path: Path) -> None:
    """W5 (D-519): w08, w09 and w12 to w14 are proven without a model, from files built here."""
    import datetime

    import openpyxl
    from docx import Document
    from openpyxl.chart import BarChart, LineChart, Reference
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.styles import Font, PatternFill
    from pypdf import PdfReader, PdfWriter

    workspace = _workspace(tmp_path)
    seeds = Path(__file__).resolve().parent / "benchmarks" / "documents"
    for check in (
        bench.check_w08,
        bench.check_w09,
        bench.check_w10,
        bench.check_w12,
        bench.check_w13,
        bench.check_w14,
    ):
        assert not check(workspace)["delivered"]

    # w08: the table from the PDF as an Excel sheet with a total formula and the yearly total in words
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Quarter", "Sales", "Orders"])
    for row in [["Q1", 41200, 3100], ["Q2", 45800, 3380], ["Q3", 52300, 3790], ["Q4", 61900, 4410]]:
        sheet.append(row)
    sheet.append(["Total", "=SUM(B2:B5)", "=SUM(C2:C5)"])
    sheet["A8"] = "Total sales for the year were 201,200 GBP."
    book.save(workspace / "project" / "figures.xlsx")
    assert bench.check_w08(workspace)["checks_failed"] == []

    # w09: the three seed PDFs in the asked order with the title set
    writer = PdfWriter()
    for name in ("cover.pdf", "terms.pdf", "annex.pdf"):
        for page in PdfReader(str(seeds / "w09_pdf_merge" / "seed" / name)).pages:
            writer.add_page(page)
    writer.add_metadata({"/Title": "Proposal pack"})
    with open(workspace / "project" / "pack.pdf", "wb") as handle:
        writer.write(handle)
    assert bench.check_w09(workspace)["checks_failed"] == []

    # w10: the seed form with its four fields filled
    reader = PdfReader(str(seeds / "w10_pdf_form" / "seed" / "form.pdf"))
    writer = PdfWriter()
    writer.append(reader)
    writer.update_page_form_field_values(
        writer.pages[0],
        {
            "full_name": "Priya Raman",
            "email": "priya.raman@example.org",
            "postcode": "MB3 4QF",
            "start_date": "8 January 2027",
        },
    )
    with open(workspace / "project" / "form-filled.pdf", "wb") as handle:
        writer.write(handle)
    assert bench.check_w10(workspace)["checks_failed"] == []

    # w12: the seed minutes with the first date changed and one row added
    document = Document(str(seeds / "w12_word_edit" / "seed" / "minutes.docx"))
    first = next(p for p in document.paragraphs if p.text.startswith("Meeting date"))
    first.runs[0].text = first.runs[0].text.replace("3 March", "10 March")
    row = document.tables[0].add_row()
    for cell, text in zip(row.cells, ["Sam", "Send the notes", "14 March"], strict=True):
        cell.text = text
    document.save(workspace / "project" / "minutes-updated.docx")
    assert bench.check_w12(workspace)["checks_failed"] == []

    # w13: the workbook rebuilt with a margin column, its chart, number formats and bold header kept (openpyxl drops charts it reads, so build it whole)
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Sales"
    sheet.append(["Product", "Revenue", "Cost", "Margin"])
    for index, row in enumerate(
        [["Kettle", 5200, 3100], ["Toaster", 3400, 2200], ["Blender", 4100, 2500], ["Grinder", 2900, 1700]],
        start=2,
    ):
        sheet.append([*row, f"=B{index}-C{index}"])
    sheet.append(["Total", "=SUM(B2:B5)", "=SUM(C2:C5)", "=B6-C6"])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for cells in sheet.iter_rows(min_row=2, min_col=2, max_col=4):
        for cell in cells:
            cell.number_format = "#,##0"
    chart = BarChart()
    chart.add_data(Reference(sheet, min_col=2, min_row=1, max_row=5), titles_from_data=True)
    sheet.add_chart(chart, "F2")
    book.save(workspace / "project" / "sales-margin.xlsx")
    assert bench.check_w13(workspace)["checks_failed"] == []

    # w14: data, KPI formulas, two charts and a conditional format
    book = openpyxl.Workbook()
    data = book.active
    data.title = "Data"
    data.append(["Month", "Revenue", "Customers", "Refunds"])
    for index, (revenue, customers, refunds) in enumerate(
        [
            (41200, 310, 12),
            (43800, 322, 9),
            (47100, 340, 15),
            (45200, 336, 11),
            (49900, 361, 8),
            (52300, 378, 10),
        ],
        start=1,
    ):
        data.append([datetime.date(2026, index, 1), revenue, customers, refunds])
    data.conditional_formatting.add(
        "D2:D7",
        CellIsRule(operator="greaterThan", formula=["12"], fill=PatternFill("solid", start_color="FFC7CE")),
    )
    kpi = book.create_sheet("KPIs")
    kpi["A1"], kpi["B1"] = "Total revenue", "=SUM(Data!B2:B7)"
    kpi["A2"], kpi["B2"] = "Average customers", "=AVERAGE(Data!C2:C7)"
    kpi["A3"], kpi["B3"] = "Refund rate", "=SUM(Data!D2:D7)/SUM(Data!C2:C7)"
    bars = BarChart()
    bars.add_data(Reference(data, min_col=2, min_row=1, max_row=7), titles_from_data=True)
    kpi.add_chart(bars, "D2")
    line = LineChart()
    line.add_data(Reference(data, min_col=3, min_row=1, max_row=7), titles_from_data=True)
    kpi.add_chart(line, "D20")
    book.save(workspace / "project" / "dashboard.xlsx")
    assert bench.check_w14(workspace)["checks_failed"] == []
