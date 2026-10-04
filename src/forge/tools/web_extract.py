"""Turning what a fetch returned into readable text (D-209): HTML (Trafilatura when installed, else a small
in-house converter), PDF (pypdfium2) and plain text. Each step falls back to the next, so a missing optional
package or an odd page costs quality, never the whole result."""

from __future__ import annotations

import contextlib
import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

THIN_CHARS = 300  # less readable text than this usually means a page that builds itself with JavaScript
MAX_PDF_PAGES = 80
_NEEDS_SCRIPT = re.compile(r"enable javascript|javascript (is )?(required|disabled)|turn on javascript", re.I)


class ExtractError(Exception):
    """Content that cannot be turned into text (a binary type)."""


@dataclass
class Extracted:
    title: str
    text: str
    method: str  # trafilatura | basic | pdf | text
    note: str = ""


class _TextExtractor(HTMLParser):
    """Readable text from HTML: skips scripts/styles/navigation, keeps headings, paragraphs, list items,
    code blocks and link targets."""

    SKIP = frozenset({"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe"})
    BLOCK = frozenset(
        {
            "p",
            "div",
            "section",
            "article",
            "br",
            "tr",
            "table",
            "ul",
            "ol",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
        }
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skipping = 0
        self.in_pre = False
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self.skipping += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "pre":
            self.in_pre = True
            self.parts.append("\n```\n")
        elif tag == "li":
            self.parts.append("\n- ")
        elif tag in ("h1", "h2", "h3"):
            self.parts.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP:
            self.skipping = max(0, self.skipping - 1)
        elif tag == "title":
            self._in_title = False
        elif tag == "pre":
            self.in_pre = False
            self.parts.append("\n```\n")
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif not self.skipping:
            self.parts.append(data if self.in_pre else re.sub(r"\s+", " ", data))

    def text(self) -> str:
        joined = "".join(self.parts)
        return re.sub(r"\n\s*\n\s*\n+", "\n\n", joined).strip()


def html_to_text(page: str) -> tuple[str, str]:
    parser = _TextExtractor()
    parser.feed(page)
    return html.unescape(parser.title.strip()), parser.text()


def is_thin(text: str) -> bool:
    stripped = text.strip()
    return len(stripped) < THIN_CHARS or (len(stripped) < 1500 and bool(_NEEDS_SCRIPT.search(stripped)))


def _trafilatura(page: str, url: str) -> tuple[str, str] | None:
    """Main content as Markdown (headings, code blocks, links and tables kept); None when the package is not
    installed or finds nothing."""
    try:
        import trafilatura
    except ImportError:
        return None
    try:
        text = trafilatura.extract(
            page,
            url=url,
            output_format="markdown",
            include_links=True,
            include_tables=True,
            include_comments=False,
            favor_recall=True,
        )
        title = ""
        with contextlib.suppress(Exception):
            meta: Any = trafilatura.extract_metadata(page)
            title = (getattr(meta, "title", "") or "") if meta is not None else ""
    except Exception:  # a parser bug on one odd page must not lose the fetch
        return None
    return (title, text) if text else None


def from_html(page: str, url: str = "") -> Extracted:
    basic_title, basic_text = html_to_text(page)
    smart = _trafilatura(page, url)
    if smart is not None and len(smart[1]) >= len(basic_text) * 0.5:
        return Extracted(smart[0] or basic_title, smart[1], "trafilatura")
    return Extracted(basic_title, basic_text, "basic")


def from_pdf(data: bytes) -> Extracted:
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return Extracted("", "", "pdf", "reading PDFs needs the pypdfium2 package")
    try:
        document = pdfium.PdfDocument(data)
        pages = []
        for index in range(min(len(document), MAX_PDF_PAGES)):
            textpage = document[index].get_textpage()
            pages.append(textpage.get_text_range().strip())
        total = len(document)
    except Exception as error:
        return Extracted("", "", "pdf", f"the PDF could not be read ({type(error).__name__})")
    text = "\n\n".join(page for page in pages if page)
    note = ""
    if not text:
        note = "the PDF has no text layer (a scan); download it and read it with ocr_image"
    elif total > MAX_PDF_PAGES:
        note = f"only the first {MAX_PDF_PAGES} of {total} pages were read"
    return Extracted("", text, "pdf", note)


def extract(content_type: str, data: bytes, text: str, url: str) -> Extracted:
    """data = the raw body, text = it decoded by the HTTP client."""
    kind = content_type.split(";")[0].strip().lower()
    if "html" in kind or (not kind and "<html" in text[:2000].lower()):
        return from_html(text, url)
    if kind == "application/pdf" or data[:5] == b"%PDF-":
        return from_pdf(data)
    if kind.startswith("text/") or "json" in kind or "xml" in kind:
        return Extracted("", text, "text")
    raise ExtractError(f"unsupported content type {kind or 'unknown'} ({len(data)} bytes)")
