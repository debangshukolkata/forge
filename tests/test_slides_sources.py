"""D-338: Word, Excel, CSV and PDF files are read into a digest that says where every fact came from (P2.19)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

docx = pytest.importorskip("docx")
openpyxl = pytest.importorskip("openpyxl")
pytest.importorskip("pypdf")
pytest.importorskip("reportlab")

from forge.slides.sources import SourceError, describe_digest, numbers_in, read_source  # noqa: E402


def _word() -> bytes:
    document = docx.Document()
    document.core_properties.title = "Annual report"
    document.add_heading("Results", level=1)
    document.add_paragraph("Revenue grew 14% to $4.2m in 2025, with 38 customers added.")
    document.add_paragraph("Churn stayed at 2%.", style="List Bullet")
    table = document.add_table(rows=3, cols=2)
    for r, row in enumerate((("Region", "Revenue"), ("North", "120"), ("South", "95"))):
        for c, value in enumerate(row):
            table.cell(r, c).text = value
    document.add_heading("Risks", level=2)
    document.add_paragraph("Supply is the main risk.")
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def _excel() -> bytes:
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Sales"
    sheet.append(["Month", "Units", "Revenue"])
    for row in (("Jan", 10, 120.5), ("Feb", 14, 150.0), ("Mar", 9, 98.25), ("Apr", 20, 210.0)):
        sheet.append(list(row))
    notes = book.create_sheet("Notes")
    notes.append(["Note"])
    notes.append(["Prepared by finance"])
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def _pdf(pages: tuple[str, ...]) -> bytes:
    from reportlab.pdfgen import canvas

    out = io.BytesIO()
    sheet = canvas.Canvas(out)
    for text in pages:
        if text:
            sheet.drawString(72, 750, text)
        sheet.showPage()
    sheet.save()
    return out.getvalue()


def test_word_headings_text_bullets_tables_and_numbers() -> None:
    digest = read_source("report.docx", _word())
    titles = [s.title for s in digest.sections]
    assert "Results" in titles and "Risks" in titles
    results = next(s for s in digest.sections if s.title == "Results")
    assert results.level == 1 and results.where == "section 'Results'"
    assert any("Revenue grew" in p for p in results.paragraphs) and results.bullets == ["Churn stayed at 2%."]
    assert results.tables == [[["Region", "Revenue"], ["North", "120"], ["South", "95"]]]
    assert numbers_in(results.paragraphs[0]) == ["14%", "$4.2m", "2025", "38"]
    text = describe_digest(digest)
    assert (
        "[section 'Results']" in text
        and "numbers: 14%, $4.2m" in text
        and "table 3 x 2: Region | Revenue" in text
    )


def test_excel_sheets_numeric_columns_and_chart_ready_series_with_their_cells() -> None:
    digest = read_source("sales.xlsx", _excel())
    sales = digest.sheets[0]
    assert sales.name == "Sales" and sales.rows == 4 and sales.columns == ["Month", "Units", "Revenue"]
    units = next(c for c in sales.numeric if c.name == "Units")
    assert (units.minimum, units.maximum, units.total, units.last, units.cells) == (9, 20, 53, 20, "B2:B5")
    assert sales.series["categories"] == ["Jan", "Feb", "Mar", "Apr"]  # type: ignore[index]
    assert [s["name"] for s in sales.series["series"]] == ["Units", "Revenue"]  # type: ignore[index]
    assert "sheet 'Sales'" in sales.series["from"]  # type: ignore[index]
    assert digest.sheets[1].series is None  # a one-column text sheet is not a chart
    text = describe_digest(digest)
    assert (
        "chart-ready: categories ['Jan', 'Feb', 'Mar', 'Apr']" in text
        and "Units (B2:B5): min 9, max 20, total 53, last 20" in text
    )


def test_csv_with_semicolons_and_a_bom_is_read_like_a_sheet() -> None:
    data = "﻿Region;Revenue;Margin\nNorth;120;12%\nSouth;95;9%\nEast;70;11%\n".encode()
    digest = read_source("regions.csv", data)
    sheet = digest.sheets[0]
    assert sheet.columns == ["Region", "Revenue", "Margin"] and sheet.rows == 3
    assert [c.name for c in sheet.numeric] == ["Revenue", "Margin"] and sheet.series is not None


def test_pdf_text_per_page_and_a_scan_is_called_a_scan() -> None:
    digest = read_source("paper.pdf", _pdf(("First page about growth 12%", "Second page")))
    assert digest.pages[0].startswith("First page about growth") and "[page 2]" in describe_digest(digest)
    scan = read_source("scan.pdf", _pdf(("",)))
    assert scan.notes and "scan" in scan.notes[0]


def test_unreadable_and_unknown_files_say_what_to_do() -> None:
    with pytest.raises(SourceError, match=r"only .docx"):
        read_source("old.doc", b"x")
    with pytest.raises(SourceError, match="could not be read as a Word document"):
        read_source("broken.docx", b"not a docx")
    with pytest.raises(SourceError, match="could not be read as an Excel workbook"):
        read_source("broken.xlsx", b"not an xlsx")
    with pytest.raises(SourceError, match="could not be read as a PDF"):
        read_source("broken.pdf", b"not a pdf")


async def test_the_tool_reads_a_file_and_refuses_a_missing_one(original_repo: Path, tmp_path: Path) -> None:
    from forge.toolkit.base import ToolContext
    from forge.tools.presentation_sources import ReadSourceDocument
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_bytes("data/report.docx", _word(), "x")
    context = ToolContext(workspace=workspace)
    result = await ReadSourceDocument().run(ReadSourceDocument.Args(path="data/report.docx"), context)
    assert result.ok and "Source report.docx (word)" in result.content
    assert not (await ReadSourceDocument().run(ReadSourceDocument.Args(path="data/none.docx"), context)).ok
