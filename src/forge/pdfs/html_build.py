"""PDFs in any script (TODO W3, D-374).

reportlab's standard fonts draw Latin text only, and it does not shape Indic or Arabic scripts (matras and conjuncts land in the wrong place even with a font
that has the glyphs). A browser engine does shape them. So an outline that contains Bengali, Devanagari and the other non-Latin scripts is laid out as HTML and
printed to PDF by headless Edge or Chrome, with the bundled Noto fonts (SIL OFL) for Bengali and Devanagari and the system's fonts for the rest. The outline is
the same one `build_pdf` takes; the result has the title and language set and the fonts embedded by the browser.

Without a browser the caller gets a clear `HtmlUnavailable` and falls back to reportlab with a warning that some glyphs may be missing."""

from __future__ import annotations

import base64
from collections.abc import Callable
from html import escape
from pathlib import Path

from forge.brand.kit import Resolved
from forge.pdfs.read import PdfError

SCRIPTS: dict[str, tuple[tuple[int, int], ...]] = {
    "Devanagari": ((0x0900, 0x097F), (0xA8E0, 0xA8FF)),
    "Bengali": ((0x0980, 0x09FF),),
    "Gurmukhi": ((0x0A00, 0x0A7F),),
    "Gujarati": ((0x0A80, 0x0AFF),),
    "Odia": ((0x0B00, 0x0B7F),),
    "Tamil": ((0x0B80, 0x0BFF),),
    "Telugu": ((0x0C00, 0x0C7F),),
    "Kannada": ((0x0C80, 0x0CFF),),
    "Malayalam": ((0x0D00, 0x0D7F),),
    "Thai": ((0x0E00, 0x0E7F),),
    "Arabic": ((0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)),
    "Hebrew": ((0x0590, 0x05FF),),
    "Greek": ((0x0370, 0x03FF),),
    "Cyrillic": ((0x0400, 0x04FF),),
    "CJK": ((0x3040, 0x30FF), (0x4E00, 0x9FFF), (0xAC00, 0xD7AF)),
}
RIGHT_TO_LEFT = {"Arabic", "Hebrew"}
SKILL_FONTS = Path(__file__).resolve().parents[1] / "skills" / "ui-design-quality" / "fonts"
BUNDLED = {  # script -> (family name, font file inside SKILL_FONTS, the Latin file of the same family)
    "Bengali": (
        "Noto Sans Bengali",
        "noto-sans-bengali/noto-sans-bengali-bengali-wght-normal.woff2",
        "noto-sans-bengali/noto-sans-bengali-latin-wght-normal.woff2",
    ),
    "Devanagari": (
        "Noto Sans Devanagari",
        "noto-sans-devanagari/noto-sans-devanagari-devanagari-wght-normal.woff2",
        "noto-sans-devanagari/noto-sans-devanagari-latin-wght-normal.woff2",
    ),
}
SYSTEM_STACK = '"Segoe UI","Nirmala UI","Leelawadee UI","Microsoft YaHei UI","Malgun Gothic","Yu Gothic UI","Arial",sans-serif'


class HtmlUnavailable(PdfError):
    """No headless browser on this machine: the caller falls back to reportlab."""


def scripts_in(texts: list[str]) -> list[str]:
    """The non-Latin scripts that appear in the given strings, in the order of SCRIPTS."""
    found: set[str] = set()
    for text in texts:
        for char in text:
            code = ord(char)
            if code < 0x0370:
                continue
            for name, ranges in SCRIPTS.items():
                if any(low <= code <= high for low, high in ranges):
                    found.add(name)
    return [name for name in SCRIPTS if name in found]


def spec_texts(spec: object) -> list[str]:
    """Every string of an outline that ends up on the page (title, footer, blocks)."""
    from forge.pdfs.build import Bullets, Heading, Image, Numbered, Paragraph, PdfSpec, Table

    assert isinstance(spec, PdfSpec)
    texts = [spec.title, spec.author, spec.footer]
    for block in spec.blocks:
        if isinstance(block, Heading | Paragraph):
            texts.append(block.text)
        elif isinstance(block, Bullets | Numbered):
            texts.extend(block.items)
        elif isinstance(block, Table):
            texts.extend(block.header)
            for row in block.rows:
                texts.extend(row)
        elif isinstance(block, Image):
            texts.append(block.caption)
    return texts


def _font_face(family: str, file: str, unicode_range: str | None = None) -> str:
    data = base64.b64encode((SKILL_FONTS / file).read_bytes()).decode("ascii")
    ranges = f"unicode-range:{unicode_range};" if unicode_range else ""
    return f'@font-face{{font-family:"{family}";src:url(data:font/woff2;base64,{data}) format("woff2");font-weight:100 900;{ranges}}}'


def colour(value: str | None, default: str) -> str:
    return "#" + (value or default)


def to_html(spec: object, scripts: list[str], load: Callable[[str], bytes]) -> str:
    """The outline as one HTML page (A4 or Letter print layout)."""
    from forge.pdfs.build import (
        Bullets,
        Heading,
        Image,
        Numbered,
        PageBreak,
        Paragraph,
        PdfSpec,
        Table,
        _link,
    )

    assert isinstance(spec, PdfSpec)
    brand = Resolved(spec.brand)
    families: list[str] = []
    faces: list[str] = []
    for script in scripts:
        if script in BUNDLED:
            family, file, _latin = BUNDLED[script]
            if (SKILL_FONTS / file).is_file():
                faces.append(_font_face(family, file))
                families.append(f'"{family}"')
    stack = ",".join([*families, SYSTEM_STACK])
    direction = "rtl" if any(s in RIGHT_TO_LEFT for s in scripts) else "ltr"
    body: list[str] = [f"<h1 class=title>{escape(spec.title)}</h1>"]
    for block in spec.blocks:
        if isinstance(block, Heading):
            body.append(f"<h{block.level + 1}>{escape(block.text)}</h{block.level + 1}>")
        elif isinstance(block, Paragraph):
            text = escape(block.text)
            if block.link:
                _link(block.link)
                text = f'<a href="{escape(block.link, quote=True)}">{text}</a>'
            body.append(f"<p>{text}</p>")
        elif isinstance(block, Bullets):
            body.append("<ul>" + "".join(f"<li>{escape(i)}</li>" for i in block.items) + "</ul>")
        elif isinstance(block, Numbered):
            body.append("<ol>" + "".join(f"<li>{escape(i)}</li>" for i in block.items) + "</ol>")
        elif isinstance(block, Table):
            head = "".join(f"<th>{escape(c)}</th>" for c in block.header)
            rows = "".join(
                "<tr>" + "".join(f"<td>{escape(c)}</td>" for c in row) + "</tr>" for row in block.rows
            )
            body.append(f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>")
        elif isinstance(block, Image):
            data = base64.b64encode(load(block.path)).decode("ascii")
            caption = f"<figcaption>{escape(block.caption)}</figcaption>" if block.caption else ""
            body.append(
                f'<figure><img alt="{escape(block.caption or "")}" style="width:{block.width_in}in" src="data:image/png;base64,{data}">{caption}</figure>'
            )
        elif isinstance(block, PageBreak):
            body.append('<div style="break-after:page"></div>')
    size = "A4" if spec.page_size == "A4" else "Letter"
    return (
        f'<!doctype html><html lang="{escape(spec.language)}" dir="{direction}"><head><meta charset="utf-8"><title>{escape(spec.title)}</title><style>'
        f"{''.join(faces)}@page{{size:{size};margin:1in 1in 0.9in 1in}}"
        f"body{{font-family:{stack};font-size:11pt;line-height:1.5;color:{colour(brand.text, '222222')}}}"
        f"h1,h2,h3,h4{{font-family:{stack};color:{colour(brand.heading, '1F3864')};line-height:1.25;margin:1.2em 0 .4em}}h1.title{{font-size:22pt;margin-top:0}}h2{{font-size:16pt}}h3{{font-size:13pt}}h4{{font-size:11.5pt}}"
        "p{margin:0 0 .7em}ul,ol{margin:0 0 .8em;padding-inline-start:1.4em}li{margin:.15em 0}a{color:#0563C1}"
        f"table{{border-collapse:collapse;width:100%;margin:.4em 0 1em;font-size:10pt}}th{{background:{colour(brand.header_fill, '1F3864')};color:{colour(brand.header_text, 'FFFFFF')};text-align:start}}"
        "th,td{border:.5pt solid #BBBBBB;padding:4pt 6pt;vertical-align:top}tr{break-inside:avoid}figure{margin:.5em 0 1em}figcaption{font-style:italic}"
        f"</style></head><body>{''.join(body)}</body></html>"
    )


def build_pdf_html(spec: object, load: Callable[[str], bytes], scripts: list[str]) -> bytes:
    """Prints the outline through a headless browser. Raises HtmlUnavailable when none can be started."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise HtmlUnavailable(
            "playwright is not installed, so non-Latin text cannot be laid out by a browser."
        ) from error
    from forge.pdfs.build import PdfSpec

    assert isinstance(spec, PdfSpec)
    html = to_html(spec, scripts, load)
    footer = escape(spec.footer)
    template = (
        '<div style="width:100%;font-size:8pt;color:#666;padding:0 1in;display:flex;justify-content:space-between">'
        f'<span>{footer}</span><span>Page <span class="pageNumber"></span></span></div>'
    )
    header = "<span></span>"
    logo_path = Resolved(spec.brand).logo
    if logo_path:
        try:
            logo_bytes = load(logo_path)
        except Exception as error:
            raise PdfError(f"The brand logo {logo_path!r} could not be read: {error}") from error
        kind = "png" if logo_bytes[:4] == b"PNG" else "jpeg"
        header = (
            f'<div style="width:100%;padding:0 1in"><img style="height:1cm" '
            f'src="data:image/{kind};base64,{base64.b64encode(logo_bytes).decode("ascii")}"></div>'
        )
    with sync_playwright() as playwright:
        browser = None
        for channel in ("msedge", "chrome"):
            try:
                browser = playwright.chromium.launch(channel=channel, headless=True)
                break
            except Exception:
                continue
        if browser is None:
            raise HtmlUnavailable("No Edge or Chrome could be started for laying out the text.")
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            page.evaluate("document.fonts.ready")
            data = page.pdf(
                format="A4" if spec.page_size == "A4" else "Letter",
                print_background=True,
                display_header_footer=True,
                header_template=header,
                footer_template=template,
                margin={"top": "1in", "bottom": "0.9in", "left": "1in", "right": "1in"},
            )
        finally:
            browser.close()
    return _with_author(data, spec)


def _with_author(data: bytes, spec: object) -> bytes:
    """The browser sets the title; the author is added here when pypdf is available."""
    from forge.pdfs.build import PdfSpec

    assert isinstance(spec, PdfSpec)
    if not spec.author:
        return data
    try:
        import io

        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return data
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    writer.add_metadata({"/Author": spec.author, "/Title": spec.title})
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
