"""Change an existing Word document and keep its formatting (D-342)."""

from __future__ import annotations

import io
from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field

from forge.documents.read import open_document
from forge.documents.spec import DocumentError


class Operation(BaseModel):
    op: Literal["replace_text", "set_paragraph", "delete_paragraph", "append_paragraph", "add_comment"]
    find: str = ""
    replace: str = ""
    index: int | None = Field(
        default=None,
        description="Paragraph number from read_document's order (1 = first non-empty), for set_paragraph / delete_paragraph",
    )
    text: str = ""
    style: str = ""
    author: str = "DebCraft"


def replace_in_paragraph(paragraph: Any, find: str, replace: str) -> int:
    """Replace `find` even when Word split it over several runs; the new text takes the formatting of the run where the match starts."""
    count = 0
    while True:
        runs = list(paragraph.runs)
        text = "".join(run.text for run in runs)
        start = text.find(find)
        if start < 0 or not find:
            return count
        end = start + len(find)
        position = 0
        first = True
        for run in runs:
            run_start, run_end = position, position + len(run.text)
            position = run_end
            if run_end <= start or run_start >= end:
                continue
            before = run.text[: max(0, start - run_start)]
            after = run.text[end - run_start :] if run_end > end else ""
            run.text = before + (replace if first else "") + after
            first = False
        count += 1
        if replace and find in replace:
            return count  # the new text contains the old: stop rather than loop forever


def _all_paragraphs(document: Any) -> list[Any]:
    found = list(document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                found.extend(cell.paragraphs)
    for section in document.sections:
        found.extend(section.header.paragraphs)
        found.extend(section.footer.paragraphs)
    return found


def _numbered(document: Any) -> list[Any]:
    return [p for p in document.paragraphs if p.text.strip()]


def edit_document(data: bytes, operations: list[Operation]) -> tuple[bytes, list[str]]:
    document = open_document(data)
    done: list[str] = []
    for operation in operations:
        kind = operation.op
        if kind == "replace_text":
            if not operation.find:
                raise DocumentError("replace_text needs find")
            total = sum(
                replace_in_paragraph(p, operation.find, operation.replace) for p in _all_paragraphs(document)
            )
            if not total:
                raise DocumentError(f"The text {operation.find!r} is not in the document")
            done.append(f"replaced {total} occurrence(s) of {operation.find!r}")
        elif kind in ("set_paragraph", "delete_paragraph", "add_comment"):
            numbered = _numbered(document)
            if operation.index is None or not 1 <= operation.index <= len(numbered):
                raise DocumentError(f"index must be between 1 and {len(numbered)}")
            paragraph = numbered[operation.index - 1]
            if kind == "set_paragraph":
                runs = paragraph.runs
                if runs:
                    runs[0].text = operation.text
                    for extra in runs[1:]:
                        extra._r.getparent().remove(extra._r)
                else:
                    paragraph.add_run(operation.text)
                if operation.style:
                    paragraph.style = operation.style
                done.append(f"paragraph {operation.index} set")
            elif kind == "delete_paragraph":
                paragraph._p.getparent().remove(paragraph._p)
                done.append(f"paragraph {operation.index} deleted")
            else:
                if not hasattr(document, "add_comment"):
                    raise DocumentError("This python-docx version cannot add comments (needs 1.2 or newer)")
                document.add_comment(
                    paragraph.runs or [paragraph.add_run("")], text=operation.text, author=operation.author
                )
                done.append(f"comment added to paragraph {operation.index}")
        elif kind == "append_paragraph":
            document.add_paragraph(operation.text, style=operation.style or None)
            done.append("paragraph appended")
    out = io.BytesIO()
    document.save(out)
    return out.getvalue(), done


Loader = Callable[[str], bytes]
