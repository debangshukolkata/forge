"""PDF rendering (spec §13A.1) with pypdfium2 (BSD-3/Apache-2.0 — PyMuPDF is avoided: AGPL). Also tells
text-layer PDFs from image-only ones (spec §13A.6)."""

from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium


def page_count(path: Path) -> int:
    document = pdfium.PdfDocument(str(path))
    try:
        return len(document)
    finally:
        document.close()


def render(path: Path, out_dir: Path, pages: list[int] | None = None, dpi: int = 200) -> list[Path]:
    """1-based page numbers; returns the PNG paths."""
    document = pdfium.PdfDocument(str(path))
    try:
        wanted = pages or list(range(1, len(document) + 1))
        out_dir.mkdir(parents=True, exist_ok=True)
        written = []
        for number in wanted:
            if not 1 <= number <= len(document):
                raise ValueError(f"page {number} is out of range (1-{len(document)})")
            bitmap = document[number - 1].render(scale=dpi / 72)
            image = bitmap.to_pil()
            target = out_dir / f"{path.stem}-p{number}.png"
            image.save(target, dpi=(dpi, dpi))
            written.append(target)
        return written
    finally:
        document.close()


def has_text_layer(path: Path, page: int = 1) -> bool:
    document = pdfium.PdfDocument(str(path))
    try:
        text = document[page - 1].get_textpage().get_text_range()
        return bool(text.strip())
    finally:
        document.close()
