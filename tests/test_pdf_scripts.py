"""D-374: a PDF with Bengali, Devanagari or other non-Latin text is laid out by a browser engine with embedded fonts, not drawn as boxes by reportlab."""

from __future__ import annotations

import pytest

from forge.pdfs.build import PdfSpec, build_pdf_any, parse_pdf_spec
from forge.pdfs.html_build import scripts_in, spec_texts, to_html

OUTLINE = """
{"title": "পরীক্ষা Test", "language": "bn", "footer": "Pulse", "blocks": [
  {"type": "heading", "level": 1, "text": "স্বাস্থ্য প্রতিবেদন"},
  {"type": "paragraph", "text": "বাংলা ভাষায় একটি ছোট পরীক্ষা। Mixed with English words."},
  {"type": "heading", "level": 2, "text": "हिन्दी अनुभाग"},
  {"type": "paragraph", "text": "नमस्ते दुनिया — यह एक परीक्षण है।"},
  {"type": "bullets", "items": ["এক", "दो", "three"]},
  {"type": "table", "header": ["নাম", "संख्या"], "rows": [["ক", "१"], ["খ", "२"]]}
]}
"""


def spec() -> PdfSpec:
    return parse_pdf_spec(OUTLINE)


def test_the_scripts_in_an_outline_are_found_and_latin_text_is_not_one() -> None:
    assert scripts_in(spec_texts(spec())) == ["Devanagari", "Bengali"]
    assert scripts_in(["Plain English with café and – dashes €"]) == []
    assert set(scripts_in(["مرحبا", "שלום", "สวัสดี", "你好", "Привет", "Γειά"])) == {
        "Thai",
        "Arabic",
        "Hebrew",
        "Greek",
        "Cyrillic",
        "CJK",
    }


def test_the_html_embeds_the_bundled_fonts_for_the_scripts_present_and_escapes_text() -> None:
    page = to_html(spec(), ["Devanagari", "Bengali"], lambda name: b"")
    assert 'lang="bn"' in page and "Noto Sans Bengali" in page and "Noto Sans Devanagari" in page
    assert "font/woff2;base64," in page and "<table>" in page and "<ul>" in page
    plain = to_html(
        parse_pdf_spec('{"title": "A <b>", "blocks": [{"type": "paragraph", "text": "x < y & z"}]}'),
        [],
        lambda name: b"",
    )
    assert "A &lt;b&gt;" in plain and "x &lt; y &amp; z" in plain and "Noto Sans" not in plain


def test_latin_text_stays_on_reportlab_without_a_note() -> None:
    pytest.importorskip("reportlab")
    data, note = build_pdf_any(
        parse_pdf_spec('{"title": "Plain", "blocks": [{"type": "paragraph", "text": "Hello"}]}'),
        lambda name: b"",
    )
    assert data.startswith(b"%PDF") and note == ""
