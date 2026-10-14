"""Build a .docx from a `DocumentSpec` with python-docx (D-342)."""

from __future__ import annotations

import contextlib
import importlib
import io
from collections.abc import Callable
from typing import Any

from forge.brand.kit import Resolved
from forge.documents.spec import (
    Bullets,
    DocumentError,
    DocumentSpec,
    Heading,
    Image,
    Numbered,
    PageBreak,
    Paragraph,
    Quote,
    Table,
)

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def load_docx() -> Any:
    try:
        return importlib.import_module("docx")
    except ImportError as error:
        raise DocumentError(
            "python-docx is not installed: pip install python-docx (the forge[docs] extra)"
        ) from error


def _field(paragraph: Any, instruction: str, placeholder: str = "") -> None:
    """A Word field (page number, table of contents): Word fills it when the file is opened."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    def run_with(child: Any) -> None:
        run = paragraph.add_run()
        run._r.append(child)

    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    begin.set(qn("w:dirty"), "true")
    run_with(begin)
    code = OxmlElement("w:instrText")
    code.set(qn("xml:space"), "preserve")
    code.text = f" {instruction} "
    run_with(code)
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    run_with(separate)
    paragraph.add_run(placeholder)
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run_with(end)


def _hyperlink(paragraph: Any, text: str, url: str, bold: bool, italic: bool) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    if not url.lower().startswith(("https://", "http://", "mailto:")):
        raise DocumentError(f"Link {url!r}: only https, http and mailto addresses are allowed")
    relation = paragraph.part.relate_to(
        url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True
    )
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), relation)
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "Hyperlink")
    properties.append(style)
    colour = OxmlElement("w:color")
    colour.set(qn("w:val"), "0563C1")
    properties.append(colour)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    properties.append(underline)
    if bold:
        properties.append(OxmlElement("w:b"))
    if italic:
        properties.append(OxmlElement("w:i"))
    run.append(properties)
    content = OxmlElement("w:t")
    content.text = text
    content.set(qn("xml:space"), "preserve")
    run.append(content)
    link.append(run)
    paragraph._p.append(link)


def _paragraph(document: Any, block: Paragraph) -> None:
    from forge.documents.footnotes import add_footnote

    paragraph = document.add_paragraph()
    if block.runs:
        for run in block.runs:
            if run.link:
                _hyperlink(paragraph, run.text, run.link, run.bold, run.italic)
            else:
                made = paragraph.add_run(run.text)
                made.bold, made.italic = run.bold or None, run.italic or None
            if run.footnote:
                add_footnote(document, paragraph, run.footnote)
    else:
        paragraph.add_run(block.text)


def _table(document: Any, block: Table, brand: Resolved) -> None:
    from docx.shared import Inches, RGBColor

    if block.caption:
        caption = document.add_paragraph(block.caption, style="Caption")
        caption.paragraph_format.keep_with_next = True
    columns = max(len(block.header), *(len(r) for r in block.rows)) if block.rows else len(block.header)
    table = document.add_table(rows=1, cols=columns)
    with contextlib.suppress(KeyError):  # a template without that style keeps its default
        table.style = "Table Grid"
    for index, text in enumerate(block.header):
        cell = table.rows[0].cells[index]
        cell.text = text
        for run in cell.paragraphs[0].runs:
            run.bold = True
            if brand.header_fill and brand.header_text:
                run.font.color.rgb = RGBColor.from_string(brand.header_text)
        if brand.header_fill:
            _shade(cell, brand.header_fill)
    _repeat_header(table.rows[0])
    for row in block.rows:
        cells = table.add_row().cells
        for index, text in enumerate(row):
            cells[index].text = text
    for index, width in enumerate(block.widths_in[:columns]):
        for row in table.rows:
            row.cells[index].width = Inches(width)
    document.add_paragraph()


def _shade(cell: Any, fill: str) -> None:
    """Background colour of a table cell."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    shading = OxmlElement("w:shd")
    shading.set(qn("w:val"), "clear")
    shading.set(qn("w:color"), "auto")
    shading.set(qn("w:fill"), fill)
    cell._tc.get_or_add_tcPr().append(shading)


def _apply_brand(document: Any, brand: Resolved) -> None:
    """Company fonts and colours on the styles every heading and paragraph already uses, so nothing is formatted by hand."""
    from docx.shared import RGBColor

    for name in ("Title", "Heading 1", "Heading 2", "Heading 3", "Heading 4"):
        try:
            style = document.styles[name]
        except KeyError:
            continue
        if brand.title_font:
            style.font.name = brand.title_font
        if brand.heading:
            style.font.color.rgb = RGBColor.from_string(brand.heading)
    normal = document.styles["Normal"]
    if brand.body_font:
        normal.font.name = brand.body_font
    if brand.text:
        normal.font.color.rgb = RGBColor.from_string(brand.text)


def _repeat_header(row: Any) -> None:
    """The header row repeats on every page the table runs onto."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    properties = row._tr.get_or_add_trPr()
    flag = OxmlElement("w:tblHeader")
    flag.set(qn("w:val"), "true")
    properties.append(flag)


def _image(document: Any, block: Image, load: Callable[[str], bytes]) -> None:
    from docx.shared import Inches

    data = load(block.path)
    document.add_picture(io.BytesIO(data), width=Inches(block.width_in))
    picture = document.inline_shapes[-1]
    properties = picture._inline.docPr
    properties.set("descr", block.alt)  # the alt text screen readers read
    properties.set("title", block.alt[:60])
    document.paragraphs[-1].alignment = 1
    if block.caption:
        document.add_paragraph(block.caption, style="Caption").alignment = 1


def build_document(spec: DocumentSpec, load: Callable[[str], bytes], template: bytes | None = None) -> bytes:
    docx = load_docx()
    from docx.oxml.ns import qn
    from docx.shared import Pt

    try:
        document = docx.Document(io.BytesIO(template)) if template else docx.Document()
        if template:
            body = document.element.body
            for child in list(body):
                if child.tag != qn("w:sectPr"):
                    body.remove(child)  # the template's styles, header and footer stay; its sample text goes
        normal = document.styles["Normal"]
        if not template:
            normal.font.name, normal.font.size = spec.font, Pt(spec.font_size)
            normal.paragraph_format.space_after = Pt(6)
            normal.paragraph_format.line_spacing = 1.15
        brand = Resolved(spec.brand)
        if spec.brand:
            _apply_brand(document, brand)
        properties = document.core_properties
        properties.title, properties.author, properties.language = spec.title, spec.author, spec.language
        run_properties = normal.element.get_or_add_rPr()
        from docx.oxml import OxmlElement

        language = OxmlElement("w:lang")
        language.set(qn("w:val"), spec.language)
        run_properties.append(language)
        section = document.sections[0]
        if spec.header:
            section.header.paragraphs[0].text = spec.header
        footer = section.footer.paragraphs[0]
        if spec.footer:
            footer.text = spec.footer + ("    " if spec.page_numbers else "")
        if spec.page_numbers:
            footer.add_run("Page ")
            _field(footer, "PAGE", "1")
        document.add_heading(spec.title, level=0)
        if spec.toc:
            _field(
                document.add_paragraph(),
                'TOC \\o "1-3" \\h \\z \\u',
                "Right-click and choose Update field to fill the contents.",
            )
        for block in spec.blocks:
            if isinstance(block, Heading):
                document.add_heading(block.text, level=block.level)
            elif isinstance(block, Paragraph):
                _paragraph(document, block)
            elif isinstance(block, Bullets):
                for item in block.items:
                    document.add_paragraph(item, style="List Bullet")
            elif isinstance(block, Numbered):
                for item in block.items:
                    document.add_paragraph(item, style="List Number")
            elif isinstance(block, Table):
                _table(document, block, brand)
            elif isinstance(block, Image):
                _image(document, block, load)
            elif isinstance(block, Quote):
                document.add_paragraph(block.text, style="Intense Quote")
            elif isinstance(block, PageBreak):
                document.add_page_break()
    except DocumentError:
        raise
    except KeyError as error:
        raise DocumentError(
            f"The template lacks the style {error}; use a template with the usual Word styles or none"
        ) from error
    except Exception as error:
        raise DocumentError(
            f"The document could not be built: {type(error).__name__}: {str(error)[:300]}"
        ) from error
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()
