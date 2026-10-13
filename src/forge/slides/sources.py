"""Word, Excel, CSV and PDF files read into a digest a deck can be built from (TODO P2.19, D-338).

A deck must say what its sources say, never invented facts or numbers. `read_source` opens a document and returns a `Digest`:

- Word (.docx): the headings with the text under each (paragraphs, bullet lists), the tables, the number of pictures;
- Excel (.xlsx, .xlsm) and CSV: each sheet's header, its size, a sample of rows, and for every numeric column its minimum, maximum, total and
  last value; plus chart-ready series (first column = categories, numeric columns = series) with the cell range they came from;
- PDF (.pdf): the text of each page (a scanned PDF has none: use ocr_image on its pages).

Every fact carries where it came from (`Section 'Results'`, `sheet 'Sales' C2:C13`, `page 4`), so the deck can cite it in the speaker
notes. The libraries are the optional `docs` extra (python-docx, openpyxl, pypdf); a missing one is reported with how to install it."""

from __future__ import annotations

import csv
import importlib
import io
import re
from dataclasses import dataclass, field
from typing import Any

from forge.errors import ForgeError

MAX_ROWS = 200_000
SAMPLE_ROWS = 6
MAX_SHEETS = 12
MAX_PAGES = 400
NUMBER = re.compile(
    r"(?<![\w.])[-+]?\$?€?£?\d[\d,]*(?:\.\d+)?%?(?:\s?(?:k|m|bn|million|billion|thousand))?(?![\w])", re.I
)


class SourceError(ForgeError):
    """The document cannot be read; the message says what to do."""


@dataclass
class Section:
    title: str
    level: int
    where: str
    paragraphs: list[str] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)


@dataclass
class Column:
    name: str
    cells: str  # the range, e.g. C2:C13
    minimum: float
    maximum: float
    total: float
    last: float
    count: int


@dataclass
class SheetDigest:
    name: str
    rows: int
    columns: list[str]
    sample: list[list[str]]
    numeric: list[Column] = field(default_factory=list)
    series: dict[str, Any] | None = None  # categories and series ready for a chart, with where they came from


@dataclass
class Digest:
    name: str
    kind: str
    sections: list[Section] = field(default_factory=list)
    sheets: list[SheetDigest] = field(default_factory=list)
    pages: list[str] = field(default_factory=list)
    pictures: int = 0
    notes: list[str] = field(default_factory=list)


def _column_letter(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def numbers_in(text: str, limit: int = 8) -> list[str]:
    """Numbers with their unit as written ('4.2%', '$1.2m', '38'), in order, leaving out single digits and years used as labels."""
    found = [m.group(0).strip().rstrip(",.") for m in NUMBER.finditer(text)]
    return [n for n in found if len(re.sub(r"\D", "", n)) >= 2 or "%" in n][:limit]


# --- Word ---


def _read_docx(data: bytes, name: str) -> Digest:
    try:
        import docx  # python-docx
    except ImportError as error:
        raise SourceError(
            "python-docx is not installed: pip install python-docx (the forge[docs] extra)"
        ) from error
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as error:  # a damaged or protected file
        raise SourceError(f"{name} could not be read as a Word document ({type(error).__name__})") from error
    digest = Digest(name, "word", pictures=len(document.inline_shapes))
    current = Section(document.core_properties.title or name, 0, "start of the document")
    digest.sections.append(current)
    body = document.element.body
    paragraphs = {p._p: p for p in document.paragraphs}
    tables = {t._tbl: t for t in document.tables}
    for child in body.iterchildren():
        if child in paragraphs:
            paragraph = paragraphs[child]
            text = paragraph.text.strip()
            style = (paragraph.style.name if paragraph.style is not None else "") or ""
            heading = re.match(r"Heading (\d)", style)
            if text and (heading or style == "Title"):
                current = Section(text, int(heading.group(1)) if heading else 0, f"section '{text[:50]}'")
                digest.sections.append(current)
            elif text and (
                "List" in style or (paragraph._p.pPr is not None and paragraph._p.pPr.numPr is not None)
            ):
                current.bullets.append(text)
            elif text:
                current.paragraphs.append(text)
        elif child in tables:
            rows = [[cell.text.strip() for cell in row.cells] for row in tables[child].rows]
            if rows:
                current.tables.append(rows)
    digest.sections = [s for s in digest.sections if s.paragraphs or s.bullets or s.tables or s.level]
    return digest


# --- Excel and CSV ---


def _sheet_digest(name: str, rows: list[list[Any]]) -> SheetDigest:
    rows = [r for r in rows if any(c not in (None, "") for c in r)]
    if not rows:
        return SheetDigest(name, 0, [], [])
    header = [
        str(c).strip() if c not in (None, "") else f"column {_column_letter(i)}"
        for i, c in enumerate(rows[0])
    ]
    body = rows[1:]
    digest = SheetDigest(
        name, len(body), header, [[("" if c is None else str(c)) for c in r] for r in body[:SAMPLE_ROWS]]
    )
    numeric_columns: list[tuple[int, list[float]]] = []
    for index, column in enumerate(header):
        values: list[float] = []
        for row in body:
            cell = row[index] if index < len(row) else None
            if isinstance(cell, bool) or cell in (None, ""):
                continue
            try:
                values.append(
                    float(
                        str(cell)
                        .replace(",", "")
                        .replace("%", "")
                        .replace("$", "")
                        .replace("€", "")
                        .replace("£", "")
                    )
                )
            except ValueError:
                values = []
                break
        if len(values) >= max(2, len(body) // 2) and values:
            numeric_columns.append((index, values))
            letter = _column_letter(index)
            digest.numeric.append(
                Column(
                    column,
                    f"{letter}2:{letter}{len(body) + 1}",
                    min(values),
                    max(values),
                    round(sum(values), 4),
                    values[-1],
                    len(values),
                )
            )
    labels = [str(r[0]) for r in body if r and r[0] not in (None, "")]
    if numeric_columns and numeric_columns[0][0] != 0 and len(labels) == len(body) and 2 <= len(body) <= 40:
        series = [(header[i], values) for i, values in numeric_columns if len(values) == len(body)]
        if series:
            digest.series = {
                "categories": labels,
                "series": [{"name": n, "values": v} for n, v in series[:4]],
                "from": f"sheet '{name}' {header[0]} and {', '.join(header[i] for i, _ in numeric_columns[:4])} (rows 2 to {len(body) + 1})",
            }
    return digest


def _read_xlsx(data: bytes, name: str) -> Digest:
    try:
        openpyxl: Any = importlib.import_module("openpyxl")
    except ImportError as error:
        raise SourceError(
            "openpyxl is not installed: pip install openpyxl (the forge[docs] extra)"
        ) from error
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as error:
        raise SourceError(
            f"{name} could not be read as an Excel workbook ({type(error).__name__})"
        ) from error
    digest = Digest(name, "excel")
    for sheet in workbook.worksheets[:MAX_SHEETS]:
        rows = []
        for index, row in enumerate(sheet.iter_rows(values_only=True)):
            if index >= MAX_ROWS:
                digest.notes.append(f"sheet '{sheet.title}' was read up to row {MAX_ROWS}")
                break
            rows.append(list(row))
        digest.sheets.append(_sheet_digest(sheet.title, rows))
    if len(workbook.worksheets) > MAX_SHEETS:
        digest.notes.append(f"{len(workbook.worksheets) - MAX_SHEETS} more sheets were not read")
    return digest


def _read_csv(data: bytes, name: str) -> Digest:
    text = data.decode("utf-8-sig", errors="replace")
    dialect: Any
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [r for _, r in zip(range(MAX_ROWS), csv.reader(io.StringIO(text), dialect), strict=False)]
    return Digest(name, "csv", sheets=[_sheet_digest(name, rows)])


# --- PDF ---


def _read_pdf(data: bytes, name: str) -> Digest:
    try:
        from pypdf import PdfReader
    except ImportError as error:
        raise SourceError("pypdf is not installed: pip install pypdf (the forge[docs] extra)") from error
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise SourceError(f"{name} is password-protected: ask the user for an unprotected copy")
        pages = [(page.extract_text() or "").strip() for page in reader.pages[:MAX_PAGES]]
    except SourceError:
        raise
    except Exception as error:
        raise SourceError(f"{name} could not be read as a PDF ({type(error).__name__})") from error
    digest = Digest(name, "pdf", pages=pages)
    if not any(pages):
        digest.notes.append(
            "no text layer: this is a scan; render its pages (pdf_render) and read them with ocr_image"
        )
    return digest


def read_source(name: str, data: bytes) -> Digest:
    lowered = name.lower()
    if lowered.endswith(".docx"):
        return _read_docx(data, name)
    if lowered.endswith((".xlsx", ".xlsm")):
        return _read_xlsx(data, name)
    if lowered.endswith((".csv", ".tsv", ".txt")):
        return _read_csv(data, name)
    if lowered.endswith(".pdf"):
        return _read_pdf(data, name)
    raise SourceError(
        f"{name}: only .docx, .xlsx, .xlsm, .csv and .pdf files are read (older .doc and .xls: save them as the newer format)"
    )


# --- for the model ---


def describe_digest(digest: Digest, limit: int = 9000) -> str:
    lines = [
        f"Source {digest.name} ({digest.kind})"
        + (f", {digest.pictures} picture(s)" if digest.pictures else "")
        + ":"
    ]
    for section in digest.sections:
        lines.append(f"\n[{section.where}] {'#' * max(section.level, 1)} {section.title}")
        for text in section.paragraphs[:6]:
            numbers = numbers_in(text)
            lines.append(f"  {text[:300]}" + (f"  (numbers: {', '.join(numbers)})" if numbers else ""))
        lines += [f"  - {b[:200]}" for b in section.bullets[:8]]
        for table in section.tables:
            lines.append(
                f"  table {len(table)} x {len(table[0])}: "
                + " | ".join(table[0])
                + (f" ... first row: {' | '.join(table[1])}" if len(table) > 1 else "")
            )
    for sheet in digest.sheets:
        lines.append(f"\n[sheet '{sheet.name}'] {sheet.rows} rows; columns: {', '.join(sheet.columns)}")
        for row in sheet.sample[:SAMPLE_ROWS]:
            lines.append("  " + " | ".join(row))
        for column in sheet.numeric:
            lines.append(
                f"  {column.name} ({column.cells}): min {column.minimum:g}, max {column.maximum:g}, total {column.total:g}, last {column.last:g}"
            )
        if sheet.series:
            lines.append(
                f"  chart-ready: categories {sheet.series['categories'][:8]}, series {[s['name'] for s in sheet.series['series']]} (from {sheet.series['from']})"
            )
    for number, page in enumerate(digest.pages, start=1):
        if page:
            lines.append(f"\n[page {number}] {page[:600]}")
    lines += [f"NOTE: {note}" for note in digest.notes]
    text = "\n".join(lines)
    return (
        text
        if len(text) <= limit
        else text[:limit] + f"\n... (cut at {limit} characters; read the file in parts or ask for a section)"
    )
