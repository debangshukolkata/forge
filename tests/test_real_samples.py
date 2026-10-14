"""D-346: the document tools work on real files, not only on files we made ourselves."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pypdf")
pytest.importorskip("openpyxl")
pytest.importorskip("docx")

from forge.documents.read import read_document
from forge.ooxml.check import check_package
from forge.ooxml.validate import validate_package
from forge.pdfs.read import read_pdf
from forge.sheets.check import check_workbook
from forge.sheets.read import read_workbook
from forge.slides.sources import read_source

REAL = Path(__file__).parent / "samples" / "real"


def test_government_forms_are_read_with_their_fields_and_a_warning_about_scripts() -> None:
    form = read_pdf((REAL / "f1040.pdf").read_bytes())
    assert form.pages == 2 and len(form.form_fields) > 100 and not form.scanned
    assert "1040" in form.texts[0] and form.risky
    w9 = read_pdf((REAL / "fw9.pdf").read_bytes())
    assert w9.pages == 6 and "Request for Taxpayer Identification Number" in w9.texts[0]
    table = read_pdf((REAL / "table.pdf").read_bytes())
    assert "Example table" in table.texts[0] and "Participants" in table.texts[0]


def test_a_census_workbook_with_title_lines_a_two_row_header_and_footnotes_is_understood() -> None:
    data = (REAL / "NST-EST2023-POP.xlsx").read_bytes()
    assert check_package(data).kind == "xlsx" and validate_package(data) == []
    assert read_workbook(data).sheets and check_workbook(data) == []
    sheet = read_source("census.xlsx", data).sheets[0]
    assert sheet.columns[0] == "Geographic Area"
    assert "Population Estimate (as of July 1) 2023" in sheet.columns
    assert sheet.rows >= 55 and any("Source: U.S. Census Bureau" in n for n in sheet.notes)
    assert sheet.sample[0][0] == "United States" and len(sheet.numeric) == 5
    assert sheet.numeric[-1].cells.startswith("F") and sheet.numeric[-1].maximum > 3e8


def test_a_real_word_file_with_comments_and_a_real_deck_pass_the_package_checks() -> None:
    data = (REAL / "comments-rich-para.docx").read_bytes()
    info = read_document(data)
    assert info.comments and "Text with hyperlink" in info.comments[0] and validate_package(data) == []
    deck = (REAL / "test.pptx").read_bytes()
    assert check_package(deck).kind == "pptx" and validate_package(deck) == []
