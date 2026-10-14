"""D-374 with a real browser: Bengali and Devanagari text in a built PDF (runs only where Edge or Chrome exists)."""

from __future__ import annotations

import io

import pytest

from forge.pdfs.build import build_pdf_any
from tests.test_pdf_scripts import spec


def test_bengali_and_devanagari_come_out_with_embedded_fonts_and_extractable_text() -> None:
    pytest.importorskip("playwright.sync_api")
    pypdf = pytest.importorskip("pypdf")
    import pypdfium2 as pdfium

    data, note = build_pdf_any(spec(), lambda name: b"")
    if note.startswith("WARNING"):
        pytest.skip(note)
    assert "browser engine" in note and data.startswith(b"%PDF")
    text = "\n".join(page.get_textpage().get_text_range() for page in pdfium.PdfDocument(data))
    assert "Mixed with English words" in text
    assert any(ch in text for ch in "বাংলা") and any(ch in text for ch in "नमस्ते")
    reader = pypdf.PdfReader(io.BytesIO(data))
    fonts = [
        (str(font.get_object().get("/BaseFont", "")), str(font.get_object().get("/Subtype", "")))
        for page in reader.pages
        for font in (page["/Resources"].get("/Font", {}) or {}).values()  # type: ignore[union-attr]
    ]
    # Chromium embeds the bundled variable Noto fonts as Type 3 fonts without a name; the system fonts stay named (Segoe UI, Arial). The text of both scripts must not come out of a named fallback alone.
    assert any(kind == "/Type3" or "Noto" in name for name, kind in fonts), fonts
