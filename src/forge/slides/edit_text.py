"""Text that keeps its look when it is replaced (shared by the edit operations)."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def set_frame_text(frame: Any, lines: list[str]) -> None:
    first = frame.paragraphs[0]
    paragraph_properties = first._p.pPr
    run_properties = first.runs[0]._r.rPr if first.runs else None
    for extra in frame.paragraphs[1:]:
        extra._p.getparent().remove(extra._p)
    for child in list(first._p):
        if not child.tag.endswith(("}pPr", "}endParaRPr")):
            first._p.remove(child)
    for index, line in enumerate(lines or [""]):
        paragraph = first if index == 0 else frame.add_paragraph()
        if index > 0 and paragraph_properties is not None:
            paragraph._p.insert(0, deepcopy(paragraph_properties))
        body = line.lstrip(" ")
        run = paragraph.add_run()
        run.text = body
        if run_properties is not None:
            existing = run._r.rPr
            if existing is not None:
                run._r.remove(existing)
            run._r.insert(0, deepcopy(run_properties))
        paragraph.level = min((len(line) - len(body)) // 2, 8)
