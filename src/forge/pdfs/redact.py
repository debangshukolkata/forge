"""True redaction of a PDF (TODO W3, D-373).

Drawing a black box over text leaves the text in the file: anyone can select or extract it. Redaction here removes it: every page is rendered to a picture, the
matches are blacked out in the picture, and a new PDF is built from the pictures. The result has no text layer at all (nothing to leak), no metadata and no
form fields, links or attachments of the original; it is a flat document. Search it again with `ocr_pdf` if needed, after the redaction.

Matches come from exact terms (case-insensitive) and from named patterns for common personal data. A page that has no text layer (a scan) cannot be searched
by term: its regions must be given by the person, and `redact` says which pages had no text."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from forge.errors import ForgeError

# Loose on purpose: a redaction that misses is worse than one that blacks out too much. Each is checked against the page text, then located on the page.
PATTERNS: dict[str, str] = {
    "email": r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+",
    "phone": r"(?<!\d)(?:\+\d{1,3}[ -]?)?(?:\(?\d{2,5}\)?[ -]?)?\d{3,5}[ -]?\d{3,5}(?!\d)",
    "card": r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)",
    "iban": r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?\b",
    "aadhaar": r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)",
    "pan": r"\b[A-Z]{5}\d{4}[A-Z]\b",
    "ssn": r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)",
    "date_of_birth": r"(?<!\d)\d{1,2}[/.-]\d{1,2}[/.-](?:19|20)\d{2}(?!\d)",
}
PADDING_POINTS = 2.0


class RedactError(ForgeError):
    """A redaction that cannot be done (unreadable file, unknown pattern, nothing to redact with)."""


@dataclass
class RedactionReport:
    pages: int = 0
    boxes: int = 0
    per_term: dict[str, int] = field(default_factory=dict)
    pages_without_text: list[int] = field(default_factory=list)
    text_left: bool = False

    def summary(self) -> str:
        lines = [f"{self.boxes} box(es) on {self.pages} page(s)."]
        for term, count in self.per_term.items():
            lines.append(f"  {term}: {count}")
        if self.pages_without_text:
            lines.append(
                f"No text layer on page(s) {', '.join(str(p) for p in self.pages_without_text)}: terms and patterns cannot find anything there; give regions for them."
            )
        return "\n".join(lines)


def _matches(text: str, terms: list[str], patterns: list[str]) -> list[tuple[str, str]]:
    """(label, exact string as it appears on the page) for every term and pattern hit in the page text."""
    found: list[tuple[str, str]] = []
    for term in terms:
        if term.strip():
            found.append((term, term))
    for name in patterns:
        expression = PATTERNS.get(name)
        if expression is None:
            raise RedactError(f"Unknown pattern {name!r}. Patterns: {', '.join(PATTERNS)}.")
        for hit in re.finditer(expression, text):
            value = hit.group(0).strip()
            if len(re.sub(r"\D", "", value)) >= 6 or name in ("email", "pan", "iban"):
                found.append((name, value))
    return found


def _line_boxes(
    characters: list[tuple[float, float, float, float]],
) -> list[tuple[float, float, float, float]]:
    """One box per line of a match: the union of its characters' boxes (characters with no size, such as a line break, are skipped)."""
    lines: list[list[float]] = []
    for left, bottom, right, top in characters:
        if right <= left or top <= bottom:
            continue
        centre = (bottom + top) / 2
        for line in lines:
            if abs((line[1] + line[3]) / 2 - centre) < 0.6 * (top - bottom):
                line[0], line[1], line[2], line[3] = (
                    min(line[0], left),
                    min(line[1], bottom),
                    max(line[2], right),
                    max(line[3], top),
                )
                break
        else:
            lines.append([left, bottom, right, top])
    return [(a, b, c, d) for a, b, c, d in lines]


def redact(
    data: bytes,
    terms: list[str] | None = None,
    patterns: list[str] | None = None,
    regions: list[tuple[int, float, float, float, float]] | None = None,
    dpi: int = 200,
    password: str = "",
) -> tuple[bytes, RedactionReport]:
    """Returns the new PDF and what was done. `regions` are (page number from 1, left, bottom, right, top) in PDF points."""
    try:
        import pypdfium2 as pdfium
        from PIL import ImageDraw
    except ImportError as error:
        raise RedactError(
            "Redaction needs pypdfium2 and Pillow (both are installed with DebCraft)."
        ) from error
    terms, patterns, regions = terms or [], patterns or [], regions or []
    if not terms and not patterns and not regions:
        raise RedactError("Give at least one term, pattern or region to redact.")
    try:
        document = pdfium.PdfDocument(data, password=password or None)
    except Exception as error:
        raise RedactError(f"Cannot open the PDF: {str(error).splitlines()[0]}") from error
    report = RedactionReport(pages=len(document))
    scale = dpi / 72.0
    pictures = []
    for number, page in enumerate(document, start=1):
        _, height = page.get_size()
        picture = page.render(scale=scale).to_pil().convert("RGB")
        draw = ImageDraw.Draw(picture)
        boxes: list[tuple[float, float, float, float]] = []
        textpage = page.get_textpage()
        text = textpage.get_text_range()
        if not text.strip():
            report.pages_without_text.append(number)
        else:
            for label, value in _matches(text, terms, patterns):
                searcher = textpage.search(value, match_case=False)
                while True:
                    hit = searcher.get_next()
                    if hit is None:
                        break
                    start, count = hit
                    for left, bottom, right, top in _line_boxes(
                        [textpage.get_charbox(i, loose=True) for i in range(start, start + count)]
                    ):
                        boxes.append((left, bottom, right, top))
                        report.per_term[label] = report.per_term.get(label, 0) + 1
        for target, left, bottom, right, top in regions:
            if target == number:
                boxes.append((left, bottom, right, top))
                report.per_term["region"] = report.per_term.get("region", 0) + 1
        for left, bottom, right, top in boxes:
            draw.rectangle(
                [
                    (left - PADDING_POINTS) * scale,
                    (height - top - PADDING_POINTS) * scale,
                    (right + PADDING_POINTS) * scale,
                    (height - bottom + PADDING_POINTS) * scale,
                ],
                fill=(0, 0, 0),
            )
        report.boxes += len(boxes)
        pictures.append(picture)
    document.close()
    buffer = io.BytesIO()
    pictures[0].save(
        buffer,
        format="PDF",
        save_all=True,
        append_images=pictures[1:],
        resolution=float(dpi),
        title="",
        author="",
        subject="",
        creator="",
        producer="",
    )
    result = buffer.getvalue()
    report.text_left = _has_text(result)
    return result, report


def _has_text(data: bytes) -> bool:
    """The proof: a text layer in the result would be a leak."""
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(data)
    try:
        return any(page.get_textpage().get_text_range().strip() for page in document)
    finally:
        document.close()
