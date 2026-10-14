"""Accept or reject the tracked changes of a Word document (D-344), in the body, tables, headers and footers.

Accept: insertions stay as normal text, deletions go. Reject: insertions go, deleted text comes back. A formatting change keeps its new
formatting either way (only the record of the old formatting is dropped, so rejecting does not restore it; the tool says so)."""

from __future__ import annotations

from typing import Any

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _unwrap(element: Any) -> None:
    parent = element.getparent()
    index = parent.index(element)
    for child in list(element):
        parent.insert(index, child)
        index += 1
    parent.remove(element)


def _roots(document: Any) -> list[Any]:
    roots = [document.element.body]
    for section in document.sections:
        roots += [section.header._element, section.footer._element]
    return roots


def count_changes(document: Any) -> int:
    return sum(len(r.findall(f".//{W}ins")) + len(r.findall(f".//{W}del")) for r in _roots(document))


def resolve_changes(document: Any, accept: bool) -> int:
    """Resolve every tracked change; returns how many insertions and deletions were settled."""
    settled = 0
    for root in _roots(document):
        for mark in list(root.iter(f"{W}ins")):
            settled += 1
            parent = mark.getparent()
            if parent is not None and parent.tag == f"{W}rPr":  # the paragraph mark was inserted
                parent.remove(mark)
            elif accept:
                _unwrap(mark)
            else:
                mark.getparent().remove(mark)
        for mark in list(root.iter(f"{W}del")):
            settled += 1
            parent = mark.getparent()
            if (parent is not None and parent.tag == f"{W}rPr") or accept:
                parent.remove(mark)
            else:
                for text in mark.iter(f"{W}delText"):
                    text.tag = f"{W}t"
                _unwrap(mark)
        for change in list(
            root.iter(f"{W}rPrChange", f"{W}pPrChange", f"{W}tblPrChange", f"{W}sectPrChange")
        ):
            change.getparent().remove(change)
    return settled
