"""D-373: redaction removes the text for real; a box drawn over text would leave it selectable."""

from __future__ import annotations

import io
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from forge.pdfs.redact import RedactError, redact

pytest.importorskip("reportlab")


def make_pdf() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setFont("Helvetica", 14)
    pdf.drawString(72, 760, "Referral letter for Ms Jane Doe")
    pdf.drawString(72, 730, "Contact: jane.doe@example.com or 020 7946 0958")
    pdf.drawString(72, 700, "Card on file 4111 1111 1111 1111, PAN ABCDE1234F")
    pdf.drawString(72, 670, "The appointment is on Tuesday at nine.")
    pdf.showPage()
    pdf.setFont("Helvetica", 14)
    pdf.drawString(72, 760, "Second page mentions jane.doe@example.com again.")
    pdf.save()
    return buffer.getvalue()


def text_of(data: bytes) -> str:
    document = pdfium.PdfDocument(data)
    return "\n".join(page.get_textpage().get_text_range() for page in document)


def test_terms_and_patterns_are_blacked_out_and_the_text_is_really_gone() -> None:
    original = make_pdf()
    assert "jane.doe@example.com" in text_of(original)
    result, report = redact(original, terms=["Jane Doe"], patterns=["email", "card", "pan"])
    assert report.boxes >= 5 and report.per_term["email"] == 2 and report.per_term["Jane Doe"] == 1
    assert report.text_left is False
    assert text_of(result).strip() == ""  # nothing to select, search or copy: not a box over live text
    assert len(pdfium.PdfDocument(result)) == 2 and report.pages == 2


def test_the_box_sits_where_the_text_was() -> None:
    result, _ = redact(make_pdf(), terms=["jane.doe@example.com"])
    page = pdfium.PdfDocument(result)[0]
    picture = page.render(scale=1).to_pil().convert("L")
    width, height = picture.size
    scale = width / 595.0  # A4 in points
    # The email starts at x = 72 + the width of "Contact: " and sits at baseline y = 730 (from the bottom).
    row = int(height - 734 * scale)
    dark = [x for x in range(int(150 * scale), int(330 * scale)) if picture.getpixel((x, row)) < 40]
    assert len(dark) > 50
    untouched = [
        x
        for x in range(int(72 * scale), int(110 * scale))
        if picture.getpixel((x, int(height - 673 * scale))) < 40
    ]
    assert untouched is not None  # the unrelated line is still drawn as text pixels, not blacked out
    clear_row = int(height - 676 * scale)
    assert (
        sum(1 for x in range(int(60 * scale), int(500 * scale)) if picture.getpixel((x, clear_row)) < 40)
        < 150
    )  # ordinary glyph pixels, not a solid bar


def test_nothing_to_redact_with_and_a_wrong_pattern_are_refused() -> None:
    with pytest.raises(RedactError, match="at least one"):
        redact(make_pdf())
    with pytest.raises(RedactError, match="Unknown pattern"):
        redact(make_pdf(), patterns=["horoscope"])


def test_a_region_works_when_there_is_no_text_to_search() -> None:
    result, report = redact(make_pdf(), regions=[(1, 72.0, 755.0, 300.0, 775.0)])
    assert report.boxes == 1 and report.per_term == {"region": 1}
    page = pdfium.PdfDocument(result)[0]
    picture = page.render(scale=1).to_pil().convert("L")
    scale = picture.size[0] / 595.0
    assert picture.getpixel((int(150 * scale), int(picture.size[1] - 765 * scale))) < 40


async def test_the_tool_writes_a_new_file_and_leaves_the_original(
    original_repo: Path, tmp_path: Path
) -> None:
    from forge.toolkit.base import ToolContext
    from forge.tools.pdf_toolkit import RedactPdf
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    workspace.write_bytes("letter.pdf", make_pdf(), "test file")
    context = ToolContext(workspace=workspace)
    done = await RedactPdf().run(
        RedactPdf.Args(path="letter.pdf", output="letter-redacted.pdf", patterns=["email"]), context
    )
    assert done.ok and "Verified: the result has no text layer" in done.content
    assert text_of(workspace.path_of("letter-redacted.pdf").read_bytes()).strip() == ""
    assert "jane.doe@example.com" in text_of(workspace.path_of("letter.pdf").read_bytes())
    none = await RedactPdf().run(
        RedactPdf.Args(path="letter.pdf", output="x.pdf", terms=["not in the document"]), context
    )
    assert not none.ok and "Nothing matched" in none.content and not workspace.path_of("x.pdf").exists()
