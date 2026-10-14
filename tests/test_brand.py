"""D-347: one brand kit colours Word, Excel and PDF documents, and unreadable colours are corrected."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from forge.brand.kit import BrandError, BrandKit, Resolved, contrast, darken_until_readable, parse_brand

docx = pytest.importorskip("docx")
openpyxl = pytest.importorskip("openpyxl")
pytest.importorskip("pypdf")

BRAND = {"accent": "#E4A11B", "text": "333333", "title_font": "Georgia", "body_font": "Arial"}


def test_a_light_accent_is_darkened_until_headings_are_readable_and_text_on_it_is_dark() -> None:
    resolved = Resolved(BrandKit(**BRAND))
    assert contrast("FFFFFF", resolved.heading or "") >= 4.5 and resolved.header_text == "111111"
    assert (
        darken_until_readable("FFFF00") != "FFFF00"
        and contrast(darken_until_readable("FFFF00"), "FFFFFF") >= 4.5
    )
    assert Resolved(None).heading is None and Resolved(None).pdf_font(None) == "Helvetica"
    assert (
        Resolved(BrandKit(title_font="Times New Roman")).pdf_font("Times New Roman", bold=True)
        == "Times-Bold"
    )
    with pytest.raises(BrandError):
        parse_brand('{"accent": "red"}')
    with pytest.raises(BrandError):
        parse_brand('{"logo": "x.png"}')


def test_the_same_brand_reaches_a_word_document_a_workbook_and_a_pdf() -> None:
    from forge.documents.build import build_document
    from forge.documents.spec import parse_document
    from forge.pdfs.build import build_pdf, parse_pdf_spec
    from forge.sheets.build import build_workbook
    from forge.sheets.spec import parse_workbook

    blocks = [
        {"type": "heading", "text": "Summary"},
        {"type": "table", "header": ["A", "B"], "rows": [["1", "2"]]},
    ]
    word = build_document(
        parse_document(json.dumps({"title": "T", "brand": BRAND, "blocks": blocks})), lambda n: b""
    )
    document = docx.Document(io.BytesIO(word))
    heading = document.styles["Heading 1"]
    assert heading.font.name == "Georgia" and str(heading.font.color.rgb) != "000000"
    assert document.styles["Normal"].font.name == "Arial"
    assert "E4A11B" in document.element.xml and 'w:fill="E4A11B"' in document.element.xml

    book = build_workbook(
        parse_workbook(
            json.dumps(
                {"brand": BRAND, "sheets": [{"name": "S", "columns": [{"header": "x"}], "rows": [[1]]}]}
            )
        )
    )
    sheet = openpyxl.load_workbook(io.BytesIO(book))["S"]
    assert sheet["A1"].fill.start_color.rgb.endswith("E4A11B") and sheet["A1"].font.color.rgb.endswith(
        "111111"
    )
    assert sheet["A2"].font.name == "Arial"

    from forge.pdfs.read import read_pdf

    pdf = build_pdf(
        parse_pdf_spec(json.dumps({"title": "T", "brand": BRAND, "blocks": blocks})), lambda n: b""
    )
    assert read_pdf(pdf).pages == 1
    assert _has_colour(pdf, (0xE4, 0xA1, 0x1B))  # the accent fills the table header


def _has_colour(pdf: bytes, rgb: tuple[int, int, int]) -> bool:
    pdfium = pytest.importorskip("pypdfium2")
    image = pdfium.PdfDocument(pdf)[0].render(scale=1).to_pil().convert("RGB")
    return any(
        all(abs(a - b) <= 6 for a, b in zip(colour, rgb, strict=True))
        for _, colour in image.getcolors(1_000_000) or []
    )


async def test_a_brand_file_is_read_by_the_build_tools(original_repo: Path, tmp_path: Path) -> None:
    from forge.toolkit.base import ToolContext
    from forge.tools.document import BuildDocument
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_text("docs/brand.json", json.dumps({"accent": "1F3864", "title_font": "Georgia"}), "x")
    workspace.write_text(
        "docs/o.json", json.dumps({"title": "T", "blocks": [{"type": "heading", "text": "H"}]}), "x"
    )
    context = ToolContext(workspace=workspace)
    made = await BuildDocument().run(
        BuildDocument.Args(outline="docs/o.json", output="docs/a.docx", brand_file="docs/brand.json"), context
    )
    assert made.ok, made.content
    assert docx.Document(str(workspace.path_of("docs/a.docx"))).styles["Heading 1"].font.name == "Georgia"
    missing = await BuildDocument().run(
        BuildDocument.Args(outline="docs/o.json", output="docs/b.docx", brand_file="docs/none.json"), context
    )
    assert not missing.ok and "No brand file" in missing.content
