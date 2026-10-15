"""Create a PDF from an outline with reportlab (D-343)."""

from __future__ import annotations

import importlib
import io
import json
from collections.abc import Callable
from typing import Annotated, Any, Literal
from xml.sax.saxutils import escape

from pydantic import BaseModel, Field, ValidationError

from forge.brand.kit import BrandKit, Resolved
from forge.pdfs.read import PdfError


class Heading(BaseModel):
    type: Literal["heading"] = "heading"
    level: int = Field(default=1, ge=1, le=3)
    text: str


class Paragraph(BaseModel):
    type: Literal["paragraph"] = "paragraph"
    text: str
    link: str | None = None


class Bullets(BaseModel):
    type: Literal["bullets"] = "bullets"
    items: list[str]


class Numbered(BaseModel):
    type: Literal["numbered"] = "numbered"
    items: list[str]


class Table(BaseModel):
    type: Literal["table"] = "table"
    header: list[str]
    rows: list[list[str]]


class Image(BaseModel):
    type: Literal["image"] = "image"
    path: str
    width_in: float = 5.5
    caption: str = ""


class PageBreak(BaseModel):
    type: Literal["page_break"] = "page_break"


Block = Annotated[
    Heading | Paragraph | Bullets | Numbered | Table | Image | PageBreak, Field(discriminator="type")
]


class PdfSpec(BaseModel):
    title: str
    author: str = ""
    language: str = "en-GB"
    page_size: Literal["A4", "Letter"] = "A4"
    footer: str = ""
    brand: BrandKit | None = Field(
        default=None,
        description="Company colours: headings and table headers follow it; fonts map to the standard PDF fonts",
    )
    blocks: list[Block]


def parse_pdf_spec(text: str, as_yaml: bool = False) -> PdfSpec:
    try:
        if as_yaml:
            import yaml

            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
        return PdfSpec.model_validate(data)
    except (ValueError, ValidationError) as error:
        raise PdfError(f"The PDF outline is not valid: {str(error)[:600]}") from error
    except Exception as error:
        raise PdfError(f"The PDF outline could not be read: {str(error)[:300]}") from error


def _link(url: str) -> None:
    if not url.lower().startswith(("https://", "http://", "mailto:")):
        raise PdfError(f"Link {url!r}: only https, http and mailto addresses are allowed")


def build_pdf(spec: PdfSpec, load: Callable[[str], bytes]) -> bytes:
    try:
        platypus: Any = importlib.import_module("reportlab.platypus")
        styles_module: Any = importlib.import_module("reportlab.lib.styles")
        pagesizes: Any = importlib.import_module("reportlab.lib.pagesizes")
        units: Any = importlib.import_module("reportlab.lib.units")
        colors: Any = importlib.import_module("reportlab.lib.colors")
    except ImportError as error:
        raise PdfError("reportlab is not installed: pip install reportlab (the forge[docs] extra)") from error
    styles = styles_module.getSampleStyleSheet()
    body = styles["BodyText"]
    body.leading = 15
    brand = Resolved(spec.brand)
    if spec.brand:
        body.fontName = brand.pdf_font(brand.body_font)
        if brand.text:
            body.textColor = colors.HexColor("#" + brand.text)
        for name in ("Title", "Heading1", "Heading2", "Heading3"):
            styles[name].fontName = brand.pdf_font(brand.title_font or brand.body_font, bold=True)
            if brand.heading:
                styles[name].textColor = colors.HexColor("#" + brand.heading)
    story: list[Any] = [platypus.Paragraph(escape(spec.title), styles["Title"]), platypus.Spacer(1, 8)]
    try:
        for block in spec.blocks:
            if isinstance(block, Heading):
                story.append(platypus.Paragraph(escape(block.text), styles[f"Heading{block.level}"]))
            elif isinstance(block, Paragraph):
                text = escape(block.text)
                if block.link:
                    _link(block.link)
                    text = f'<link href="{escape(block.link, {chr(34): "&quot;"})}" color="#0563C1"><u>{text}</u></link>'
                story.append(platypus.Paragraph(text, body))
            elif isinstance(block, Bullets):
                story.append(
                    platypus.ListFlowable(
                        [platypus.ListItem(platypus.Paragraph(escape(i), body)) for i in block.items],
                        bulletType="bullet",
                    )
                )
            elif isinstance(block, Numbered):
                story.append(
                    platypus.ListFlowable(
                        [platypus.ListItem(platypus.Paragraph(escape(i), body)) for i in block.items],
                        bulletType="1",
                    )
                )
            elif isinstance(block, Table):
                head = styles_module.ParagraphStyle(
                    "head",
                    parent=body,
                    textColor=colors.HexColor("#" + (brand.header_text or "FFFFFF")),
                    fontName=brand.pdf_font(brand.body_font, bold=True),
                )
                cells = [[platypus.Paragraph(escape(c), head) for c in block.header]] + [
                    [platypus.Paragraph(escape(c), body) for c in row] for row in block.rows
                ]
                table = platypus.Table(cells, repeatRows=1)
                table.setStyle(
                    platypus.TableStyle(
                        [
                            (
                                "BACKGROUND",
                                (0, 0),
                                (-1, 0),
                                colors.HexColor("#" + (brand.header_fill or "1F3864")),
                            ),
                            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BBBBBB")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ]
                    )
                )
                story += [table, platypus.Spacer(1, 10)]
            elif isinstance(block, Image):
                reader = importlib.import_module("reportlab.lib.utils").ImageReader(
                    io.BytesIO(load(block.path))
                )
                width, height = reader.getSize()
                shown = block.width_in * units.inch
                story.append(
                    platypus.Image(io.BytesIO(load(block.path)), width=shown, height=shown * height / width)
                )
                if block.caption:
                    story.append(platypus.Paragraph(f"<i>{escape(block.caption)}</i>", body))
            elif isinstance(block, PageBreak):
                story.append(platypus.PageBreak())
    except PdfError:
        raise
    except Exception as error:
        raise PdfError(f"The PDF could not be built: {type(error).__name__}: {str(error)[:300]}") from error

    footer = _safe_footer(spec.footer)
    logo_reader: Any = None
    if brand.logo:
        try:
            logo_reader = importlib.import_module("reportlab.lib.utils").ImageReader(
                io.BytesIO(load(brand.logo))
            )
        except Exception as error:
            raise PdfError(f"The brand logo {brand.logo!r} could not be read: {error}") from error

    def decorate(canvas: Any, document: Any) -> None:
        canvas.saveState()
        if logo_reader is not None:
            # About one centimetre high, in the top margin, keeping the picture's proportions (D-388).
            width, height = logo_reader.getSize()
            drawn_height = 28.0
            canvas.drawImage(
                logo_reader,
                units.inch,
                document.pagesize[1] - 0.45 * units.inch - drawn_height,
                width=drawn_height * width / height,
                height=drawn_height,
                mask="auto",
            )
        canvas.setFont("Helvetica", 9)
        canvas.drawString(units.inch, 0.5 * units.inch, footer)
        canvas.drawRightString(document.pagesize[0] - units.inch, 0.5 * units.inch, f"Page {document.page}")
        canvas.restoreState()

    out = io.BytesIO()
    size = pagesizes.A4 if spec.page_size == "A4" else pagesizes.letter
    document = platypus.SimpleDocTemplate(
        out,
        pagesize=size,
        title=spec.title,
        author=spec.author,
        lang=spec.language,
        leftMargin=units.inch,
        rightMargin=units.inch,
        topMargin=units.inch,
        bottomMargin=0.9 * units.inch,
    )
    try:
        document.build(story, onFirstPage=decorate, onLaterPages=decorate)
    except Exception as error:
        raise PdfError(f"The PDF could not be built: {type(error).__name__}: {str(error)[:300]}") from error
    return out.getvalue()


def build_pdf_any(spec: PdfSpec, load: Callable[[str], bytes]) -> tuple[bytes, str]:
    """`build_pdf`, or a browser layout when the outline holds Indic, Arabic, Hebrew, Thai, CJK, Cyrillic or Greek text that reportlab's standard fonts cannot
    draw or shape (D-374). Returns the PDF and a note for the person (empty when nothing special happened)."""
    from forge.pdfs.html_build import HtmlUnavailable, build_pdf_html, scripts_in, spec_texts

    scripts = scripts_in(spec_texts(spec))
    if not scripts:
        return build_pdf(spec, load), ""
    try:
        return build_pdf_html(
            spec, load, scripts
        ), f"{', '.join(scripts)} text was laid out by the browser engine (fonts embedded)."
    except HtmlUnavailable as error:
        return (
            build_pdf(spec, load),
            f"WARNING: {error} The PDF uses standard fonts, so {', '.join(scripts)} characters may be missing or misplaced.",
        )


def _safe_footer(text: str) -> str:
    return text.encode("latin-1", errors="replace").decode("latin-1")
