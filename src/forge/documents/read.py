"""Read a Word document as Markdown-like text, with its comments and tracked changes (D-342)."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any

from forge.documents.build import load_docx
from forge.documents.spec import DocumentError

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass
class DocumentInfo:
    title: str
    language: str
    markdown: str
    comments: list[str] = field(default_factory=list)
    footnotes: list[str] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0
    pictures: int = 0
    pictures_without_alt: int = 0
    has_macros: bool = False
    package_notes: list[str] = field(default_factory=list)


def open_document(data: bytes) -> Any:
    from forge.ooxml.check import check_package

    docx = load_docx()
    check_package(data)  # refuse a hostile package before python-docx reads it (D-345)
    try:
        return docx.Document(io.BytesIO(data))
    except Exception as error:
        raise DocumentError(
            f"The file could not be read as a Word document ({type(error).__name__}); damaged or password-protected?"
        ) from error


def _comments(data: bytes) -> list[str]:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "word/comments.xml" not in archive.namelist():
                return []
            xml = archive.read("word/comments.xml").decode("utf-8", errors="replace")
    except zipfile.BadZipFile:
        return []
    found = []
    for match in re.finditer(r"<w:comment\b([^>]*)>(.*?)</w:comment>", xml, flags=re.S):
        author = re.search(r'w:author="([^"]*)"', match.group(1))
        text = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", match.group(2)))
        found.append(f"{author.group(1) if author else 'unknown'}: {text}")
    return found


def read_document(data: bytes) -> DocumentInfo:
    document = open_document(data)
    paragraphs = {p._p: p for p in document.paragraphs}
    tables = {t._tbl: t for t in document.tables}
    lines: list[str] = []
    for child in document.element.body.iterchildren():
        if child in paragraphs:
            paragraph = paragraphs[child]
            text = paragraph.text.strip()
            if not text:
                continue
            style = (paragraph.style.name if paragraph.style is not None else "") or ""
            heading = re.match(r"Heading (\d)", style)
            if heading:
                lines.append("#" * int(heading.group(1)) + " " + text)
            elif style == "Title":
                lines.append("# " + text)
            elif "List Bullet" in style:
                lines.append("- " + text)
            elif "List Number" in style:
                lines.append("1. " + text)
            else:
                lines.append(text)
        elif child in tables:
            rows = [
                [cell.text.strip().replace("\n", " ") for cell in row.cells] for row in tables[child].rows
            ]
            if rows:
                lines.append("| " + " | ".join(rows[0]) + " |")
                lines.append("|" + "---|" * len(rows[0]))
                lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        lines.append("")
    body = document.element.body
    pictures = body.findall(f".//{W}drawing")
    without_alt = 0
    for drawing in pictures:
        properties = next(
            iter(
                drawing.iter("{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr")
            ),
            None,
        )
        if properties is None or not (properties.get("descr") or "").strip():
            without_alt += 1
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        macros = any(n.endswith("vbaProject.bin") for n in archive.namelist())
    from forge.documents.footnotes import footnote_texts
    from forge.ooxml.check import check_package

    return DocumentInfo(
        document.core_properties.title or "",
        document.core_properties.language or "",
        "\n".join(lines).strip(),
        _comments(data),
        footnote_texts(document),
        len(body.findall(f".//{W}ins")),
        len(body.findall(f".//{W}del")),
        len(pictures),
        without_alt,
        macros,
        check_package(data).notes(),
    )


def describe_document(info: DocumentInfo, name: str = "document", limit: int = 12000) -> str:
    head = [
        f"{name}: title {info.title!r}, language {info.language or 'not set'}, {info.pictures} picture(s)"
    ]
    head += [f"NOTE: {note}" for note in info.package_notes]
    if info.insertions or info.deletions:
        head.append(
            f"Tracked changes: {info.insertions} insertion(s), {info.deletions} deletion(s) (the text below shows them as the final text; "
            "deleted text is not shown)."
        )
    if info.comments:
        head.append("Comments:\n" + "\n".join(f"  - {c[:300]}" for c in info.comments[:30]))
    if info.footnotes:
        head.append(
            "Footnotes:\n" + "\n".join(f"  {n}. {t[:300]}" for n, t in enumerate(info.footnotes, start=1))
        )
    text = info.markdown
    if len(text) > limit:
        text = text[:limit] + f"\n... (cut at {limit} characters)"
    return "\n".join(head) + "\n\n" + text
