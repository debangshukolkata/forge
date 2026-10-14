"""Change PDF files: merge, split, rotate, crop, delete or extract pages, watermark, page numbers, forms, encryption (D-343).
Every function takes bytes and returns new bytes: the original file is never touched."""

from __future__ import annotations

import io
import re
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

from forge.pdfs.read import PdfError, load_pypdf, open_pdf


class Operation(BaseModel):
    op: Literal[
        "merge",
        "rotate",
        "crop",
        "delete_pages",
        "extract_pages",
        "watermark",
        "page_numbers",
        "fill_form",
        "encrypt",
        "decrypt",
        "set_metadata",
    ]
    pages: str = Field(default="", description="Pages as '1-3,5' (1-based); empty = all pages")
    paths: list[str] = Field(default_factory=list, description="merge: the PDFs to append, in order")
    degrees: int = Field(default=90, description="rotate: 90, 180 or 270 clockwise")
    margins_in: tuple[float, float, float, float] = Field(
        default=(0, 0, 0, 0), description="crop: inches to cut from (left, bottom, right, top)"
    )
    text: str = Field(
        default="", description="watermark text / page number format, e.g. 'Page {n} of {total}'"
    )
    opacity: float = 0.15
    position: Literal["bottom-centre", "bottom-right", "bottom-left", "top-right"] = "bottom-centre"
    fields: dict[str, str] = Field(default_factory=dict, description="fill_form: {field name: value}")
    password: str = Field(
        default="", description="encrypt: the password to set; decrypt: the password given by the user"
    )
    title: str = ""
    author: str = ""


def parse_pages(spec: str, total: int) -> list[int]:
    """'1-3,5' -> [0, 1, 2, 4] (zero-based); empty = every page."""
    if not spec.strip():
        return list(range(total))
    found: list[int] = []
    for part in spec.split(","):
        match = re.fullmatch(r"\s*(\d+)(?:\s*-\s*(\d+))?\s*", part)
        if not match:
            raise PdfError(f"Pages {spec!r}: write them like 1-3,5")
        start, end = int(match.group(1)), int(match.group(2) or match.group(1))
        if start < 1 or end < start or end > total:
            raise PdfError(f"Pages {part.strip()!r} are outside this PDF, which has {total} page(s)")
        found.extend(range(start - 1, end))
    return list(dict.fromkeys(found))


def _write(writer: Any) -> bytes:
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _writer_from(reader: Any) -> Any:
    writer = load_pypdf().PdfWriter()
    writer.append(reader)
    return writer


def _overlay(width: float, height: float, draw: Callable[[Any], None]) -> Any:
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    sheet = canvas.Canvas(buffer, pagesize=(width, height))
    draw(sheet)
    sheet.save()
    return load_pypdf().PdfReader(io.BytesIO(buffer.getvalue())).pages[0]


def _safe_text(text: str) -> str:
    """The standard PDF fonts hold Latin-1 only; other characters become '?' rather than failing."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def apply(data: bytes, operation: Operation, load: Callable[[str], bytes]) -> bytes:
    kind = operation.op
    if kind == "decrypt":
        reader = open_pdf(data, operation.password)
        return _write(_writer_from(reader))
    reader = open_pdf(data, operation.password)
    total = len(reader.pages)
    if kind == "merge":
        if not operation.paths:
            raise PdfError("merge needs paths")
        writer = _writer_from(reader)
        for path in operation.paths:
            writer.append(open_pdf(load(path)))
        return _write(writer)
    if kind in ("delete_pages", "extract_pages"):
        chosen = parse_pages(operation.pages, total)
        keep = [i for i in range(total) if (i in chosen) == (kind == "extract_pages")]
        if not keep:
            raise PdfError("That would leave no pages")
        writer = load_pypdf().PdfWriter()
        for index in keep:
            writer.add_page(reader.pages[index])
        return _write(writer)
    writer = _writer_from(reader)
    if kind == "set_metadata":
        writer.add_metadata(
            {k: v for k, v in (("/Title", operation.title), ("/Author", operation.author)) if v}
        )
        return _write(writer)
    if kind == "encrypt":
        if not operation.password:
            raise PdfError("encrypt needs a password")
        writer.encrypt(operation.password)
        return _write(writer)
    if kind == "fill_form":
        if not operation.fields:
            raise PdfError("fill_form needs fields")
        known = set((reader.get_fields() or {}).keys())
        missing = [name for name in operation.fields if name not in known]
        if missing:
            raise PdfError(
                f"No such form field: {', '.join(missing)}. Fields: {', '.join(sorted(known)) or 'none'}"
            )
        for page in writer.pages:
            writer.update_page_form_field_values(page, operation.fields, auto_regenerate=False)
        writer.set_need_appearances_writer(True)
        return _write(writer)
    chosen = parse_pages(operation.pages, total)
    for index in chosen:
        page = writer.pages[index]
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        if kind == "rotate":
            if operation.degrees % 90:
                raise PdfError("rotate: degrees must be 90, 180 or 270")
            page.rotate(operation.degrees)
        elif kind == "crop":
            left, bottom, right, top = (m * 72 for m in operation.margins_in)
            if left + right >= width or bottom + top >= height:
                raise PdfError("crop: the margins leave nothing of the page")
            box = page.mediabox
            low_x, low_y = float(box.left), float(box.bottom)
            page.cropbox.lower_left = (low_x + left, low_y + bottom)
            page.cropbox.upper_right = (low_x + width - right, low_y + height - top)
            page.mediabox.lower_left = page.cropbox.lower_left
            page.mediabox.upper_right = page.cropbox.upper_right
        elif kind == "watermark":
            if not operation.text:
                raise PdfError("watermark needs text")
            text = _safe_text(operation.text)

            def draw(sheet: Any, w: float = width, h: float = height, t: str = text) -> None:
                sheet.saveState()
                sheet.setFillGray(0.5, operation.opacity)
                sheet.setFont("Helvetica-Bold", max(24, min(w, h) / 8))
                sheet.translate(w / 2, h / 2)
                sheet.rotate(45)
                sheet.drawCentredString(0, 0, t)
                sheet.restoreState()

            page.merge_page(_overlay(width, height, draw))
        elif kind == "page_numbers":
            label = _safe_text((operation.text or "Page {n} of {total}").format(n=index + 1, total=total))

            def number(sheet: Any, w: float = width, h: float = height, text: str = label) -> None:
                sheet.setFont("Helvetica", 9)
                if operation.position == "bottom-centre":
                    sheet.drawCentredString(w / 2, 24, text)
                elif operation.position == "bottom-right":
                    sheet.drawRightString(w - 36, 24, text)
                elif operation.position == "bottom-left":
                    sheet.drawString(36, 24, text)
                else:
                    sheet.drawRightString(w - 36, h - 30, text)

            page.merge_page(_overlay(width, height, number))
    return _write(writer)


def split_pdf(data: bytes, ranges: list[str], password: str = "") -> list[bytes]:
    """One new PDF per range, e.g. ['1-3', '4-6']."""
    reader = open_pdf(data, password)
    parts = []
    for spec in ranges:
        writer = load_pypdf().PdfWriter()
        for index in parse_pages(spec, len(reader.pages)):
            writer.add_page(reader.pages[index])
        parts.append(_write(writer))
    return parts


def extract_images(data: bytes, password: str = "", limit: int = 60) -> list[tuple[str, bytes]]:
    """(file name, bytes) of the pictures in the PDF."""
    reader = open_pdf(data, password)
    found: list[tuple[str, bytes]] = []
    for number, page in enumerate(reader.pages, start=1):
        for image in page.images:
            if len(found) >= limit:
                return found
            suffix = (image.name.rsplit(".", 1)[-1] if "." in image.name else "png").lower()
            found.append((f"page{number}-{len(found) + 1}.{suffix}", image.data))
    return found
