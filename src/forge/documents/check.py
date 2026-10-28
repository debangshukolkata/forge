"""Accessibility and structure checks for a Word document (D-342): title and language set, headings in order, no pictures without alt text,
no empty headings, tables with a header row, no heading faked with bold text, no runs of empty paragraphs used as spacing."""

from __future__ import annotations

import re

from forge.documents.read import open_document, read_document


def check_document(data: bytes) -> list[str]:
    document = open_document(data)
    info = read_document(data)
    problems: list[str] = []
    if not info.title.strip():
        problems.append(
            "The document has no title in its properties (File > Info > Title); screen readers announce it."
        )
    if not info.language.strip():
        problems.append("The document language is not set.")
    if info.pictures_without_alt:
        problems.append(f"{info.pictures_without_alt} picture(s) have no alt text.")
    last_level = 0
    empty_run = 0
    from docx.text.paragraph import Paragraph

    for child in document.element.body.iterchildren():
        if child.tag.endswith("}tbl"):
            empty_run = 0  # paragraphs on either side of a table are not a run of spacing (D-532)
            continue
        if not child.tag.endswith("}p"):
            continue
        paragraph = Paragraph(child, document)
        style = (paragraph.style.name if paragraph.style is not None else "") or ""
        text = paragraph.text.strip()
        match = re.match(r"Heading (\d)", style)
        if match:
            level = int(match.group(1))
            if not text:
                problems.append(f"An empty heading (level {level}).")
            if level > last_level + 1 and last_level:
                problems.append(f"Heading {text[:40]!r} jumps from level {last_level} to {level}.")
            last_level = level
        elif (
            text
            and len(text) < 80
            and not text.endswith((".", ":", ","))
            and paragraph.runs
            and all(run.bold for run in paragraph.runs if run.text.strip())
            and style in ("Normal", "")
            and not LABEL_LINE.match(text)
        ):
            problems.append(f"{text[:40]!r} looks like a heading made with bold text: use a Heading style.")
        empty_run = empty_run + 1 if not text and not paragraph._p.xpath(".//w:drawing") else 0
        if empty_run == 3:
            problems.append(
                "Several empty paragraphs in a row are used as spacing: set paragraph spacing instead."
            )
    for number, table in enumerate(document.tables, start=1):
        header = table.rows[0]._tr.trPr is not None and bool(header_flag(table.rows[0]))
        if len(table.rows) > 1 and not header:
            problems.append(f"Table {number} does not mark its first row as a header row.")
    return problems


# A letter's bold subject line is a label, not a heading.
LABEL_LINE = re.compile(r"^(subject|re|ref|reference|regarding|our ref|your ref)\s*:", re.IGNORECASE)


def header_flag(row: object) -> list[object]:
    return row._tr.xpath("./w:trPr/w:tblHeader")  # type: ignore[attr-defined, no-any-return]


def describe_problems(problems: list[str]) -> str:
    if not problems:
        return "No structure or accessibility problems found."
    return f"{len(problems)} problem(s):\n" + "\n".join(f"  - {p}" for p in problems)
