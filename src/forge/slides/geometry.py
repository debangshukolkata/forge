"""Where a shape is, fast (TODO P3.3, D-324). python-pptx finds the position of a placeholder that has none of its own by searching the
slide's layout and master with XPath on every read: a deck of 150 slides spent most of its checking time there. `Geometry` reads each
shape once per pass and resolves inherited positions from a per-layout table built once, with the same answer as python-pptx."""

from __future__ import annotations

from typing import Any

NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
}
Box = tuple[int | None, int | None, int | None, int | None]
NO_BOX: Box = (None, None, None, None)
# a placeholder's kind on the layout and master side: titles and bodies have several spellings
KIND = {"ctrTitle": "title", "title": "title", "subTitle": "body", "body": "body", "obj": "body", "": "body"}


def _read_box(element: Any) -> Box | None:
    """The shape's own position and size; a part it does not state (python-pptx writes `off` alone when only `left` is set) is None."""
    transform = element.xpath("./p:spPr/a:xfrm | ./p:xfrm | ./p:grpSpPr/a:xfrm")
    if not transform:
        return None
    off, ext = transform[0].find("a:off", NS), transform[0].find("a:ext", NS)

    def number(node: Any, name: str) -> int | None:
        return int(node.get(name, "0")) if node is not None and node.get(name) is not None else None

    return (number(off, "x"), number(off, "y"), number(ext, "cx"), number(ext, "cy"))


class Geometry:
    """Use one per pass over a deck (it caches by element and is never reused after the deck changed)."""

    def __init__(self) -> None:
        # The elements are kept in the values: an lxml proxy that is freed can give its id() to the next one.
        self._boxes: dict[int, tuple[Any, Box]] = {}
        self._tables: dict[int, tuple[Any, tuple[dict[str, Box], dict[str, Box]]]] = {}

    def box(self, shape: Any) -> Box:
        element = shape._element
        cached = self._boxes.get(id(element))
        if cached is None:
            cached = (element, self._resolve(shape))
            self._boxes[id(element)] = cached
        return cached[1]

    def full(self, shape: Any) -> tuple[int, int, int, int] | None:
        """The position and size when all four are known, else None."""
        left, top, width, height = self.box(shape)
        if left is None or top is None or width is None or height is None:
            return None
        return (left, top, width, height)

    def _resolve(self, shape: Any) -> Box:
        own = _read_box(shape._element)
        if own is not None and None not in own:
            return own
        if not shape.is_placeholder:
            return (shape.left, shape.top, shape.width, shape.height)
        inherited = self._inherited(shape)
        if own is None:
            return inherited
        return (
            own[0] if own[0] is not None else inherited[0],
            own[1] if own[1] is not None else inherited[1],
            own[2] if own[2] is not None else inherited[2],
            own[3] if own[3] is not None else inherited[3],
        )

    def _inherited(self, shape: Any) -> Box:
        holder = shape._element.xpath(
            "./p:nvSpPr/p:nvPr/p:ph | ./p:nvPicPr/p:nvPr/p:ph | ./p:nvGraphicFramePr/p:nvPr/p:ph"
        )
        if not holder:
            return NO_BOX
        idx, kind = holder[0].get("idx", "0"), KIND.get(holder[0].get("type", ""), holder[0].get("type", ""))
        try:
            layout = shape.part.slide_layout
        except (AttributeError, KeyError):
            return NO_BOX
        by_idx, by_kind = self._table(layout)
        if idx in by_idx:
            return by_idx[idx]
        if kind in by_kind:
            return by_kind[kind]
        _, master_kinds = self._table(layout.slide_master)
        return master_kinds.get(kind, NO_BOX)

    def _table(self, owner: Any) -> tuple[dict[str, Box], dict[str, Box]]:
        element = owner._element
        cached = self._tables.get(id(element))
        if cached is not None:
            return cached[1]
        by_idx: dict[str, Box] = {}
        by_kind: dict[str, Box] = {}
        for shape in element.xpath(".//p:sp[p:nvSpPr/p:nvPr/p:ph]"):
            holder = shape.xpath("./p:nvSpPr/p:nvPr/p:ph")[0]
            box = _read_box(shape)
            if box is None or None in box:
                continue
            by_idx.setdefault(holder.get("idx", "0"), box)
            kind = KIND.get(holder.get("type", ""), holder.get("type", ""))
            by_kind.setdefault(kind, box)
        table = (by_idx, by_kind)
        self._tables[id(element)] = (element, table)
        return table
