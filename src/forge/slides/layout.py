"""Layout containers for freeform slides (TODO P1.3, D-279): the model states intent ("three equal cards with a 0.4 gap")
and this module computes the coordinates, so slides stop colliding because of arithmetic slips.

A freeform slide's `elements` may contain containers next to ordinary elements:

    {"type": "row",    "x": 0.7, "y": 2.0, "w": 11.9, "h": 3.5, "gap": 0.4, "children": [ ... ]}
    {"type": "column", ...same fields...}
    {"type": "grid",   "x": .., "y": .., "w": .., "h": .., "cols": 3, "gap": 0.3, "children": [ ... ]}

Children are ordinary elements without x, y, w, h (a nested container also needs none). Optional keys on a child:
`weight` (its share of the free space along the container's direction, default 1), `length` (a fixed length in inches
along that direction instead), `cross` (a fixed length across the direction) and, in a grid, `colspan`. Container keys:
`gap` (inches between children, default 0.3), `pad` (inner margin, default 0) and `align` (where a child with a fixed
`cross` sits across the direction: start, center, end; default start; children without `cross` fill the cross axis).
The containers disappear after expansion: what the builder sees is plain elements with coordinates."""

from __future__ import annotations

from typing import Any

from forge.slides.diagrams import DiagramError, expand_diagram

CONTAINERS = ("row", "column", "grid")
DEFAULT_GAP = 0.3
EPSILON = 1e-6
MAX_DEPTH = 4


class LayoutError(ValueError):
    """A container cannot be laid out; the message says which one and why."""


def _number(value: Any, name: str, where: str, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise LayoutError(f"{where}: '{name}' must be a number")
    if value < minimum:
        raise LayoutError(f"{where}: '{name}' must be at least {minimum}")
    return float(value)


def _split(children: list[dict[str, Any]], available: float, where: str, axis: str) -> list[float]:
    """Lengths along the main axis: fixed `length` children keep theirs, the rest share what is left by `weight`."""
    fixed = sum(_number(c["length"], "length", where, 0.05) for c in children if "length" in c)
    weights = [0.0 if "length" in c else _number(c.get("weight", 1), "weight", where, 0.05) for c in children]
    free = available - fixed
    if free < -EPSILON:
        raise LayoutError(
            f"{where}: the children need {fixed:.2f} in of fixed {axis} but only {available:.2f} in are left after the gaps; "
            "shrink a length or the gap, or make the container larger"
        )
    total = sum(weights)
    return [
        float(c["length"]) if "length" in c else (free * w / total if total else 0.0)
        for c, w in zip(children, weights, strict=True)
    ]


def _place_cross(
    child: dict[str, Any], start: float, length: float, align: str, where: str
) -> tuple[float, float]:
    if "cross" not in child:
        return start, length
    cross = _number(child["cross"], "cross", where, 0.05)
    if cross > length + EPSILON:
        raise LayoutError(f"{where}: a child is {cross:.2f} in across but the container is {length:.2f} in")
    offset = {"start": 0.0, "center": (length - cross) / 2, "end": length - cross}[align]
    return start + offset, cross


def _clean(child: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in child.items() if k not in ("weight", "length", "cross", "colspan")}


def _expand_container(node: dict[str, Any], depth: int, where: str) -> list[dict[str, Any]]:
    if depth > MAX_DEPTH:
        raise LayoutError(
            f"{where}: containers are nested more than {MAX_DEPTH} levels deep; simplify the layout"
        )
    for key in ("x", "y", "w", "h"):
        if key not in node:
            raise LayoutError(f"{where}: a {node['type']} needs x, y, w and h (the box it fills)")
    x, y = _number(node["x"], "x", where), _number(node["y"], "y", where)
    w, h = _number(node["w"], "w", where, 0.1), _number(node["h"], "h", where, 0.1)
    gap = _number(node.get("gap", DEFAULT_GAP), "gap", where)
    pad = _number(node.get("pad", 0), "pad", where)
    align = node.get("align", "start")
    if align not in ("start", "center", "end"):
        raise LayoutError(f"{where}: 'align' must be start, center or end")
    children = node.get("children")
    if not isinstance(children, list) or not children:
        raise LayoutError(f"{where}: a {node['type']} needs a non-empty 'children' list")
    if not all(isinstance(c, dict) for c in children):
        raise LayoutError(f"{where}: every child must be an element object")
    inner_x, inner_y, inner_w, inner_h = x + pad, y + pad, w - 2 * pad, h - 2 * pad
    if inner_w <= 0 or inner_h <= 0:
        raise LayoutError(f"{where}: the padding leaves no room")
    boxes: list[tuple[dict[str, Any], float, float, float, float]] = []
    kind = node["type"]
    if kind in ("row", "column"):
        horizontal = kind == "row"
        main = inner_w if horizontal else inner_h
        cross_len = inner_h if horizontal else inner_w
        lengths = _split(
            children, main - gap * (len(children) - 1), where, "width" if horizontal else "height"
        )
        cursor = inner_x if horizontal else inner_y
        for child, length in zip(children, lengths, strict=True):
            c_start, c_len = _place_cross(child, inner_y if horizontal else inner_x, cross_len, align, where)
            boxes.append(
                (child, cursor, c_start, length, c_len)
                if horizontal
                else (child, c_start, cursor, c_len, length)
            )
            cursor += length + gap
    else:
        cols = int(_number(node.get("cols", 0), "cols", where, 1))
        spans = [int(_number(c.get("colspan", 1), "colspan", where, 1)) for c in children]
        if max(spans) > cols:
            raise LayoutError(f"{where}: a colspan is larger than the {cols} columns")
        rows: list[list[int]] = [[]]
        used = 0
        for index, span in enumerate(spans):
            if used + span > cols:
                rows.append([])
                used = 0
            rows[-1].append(index)
            used += span
        cell_w = (inner_w - gap * (cols - 1)) / cols
        cell_h = (inner_h - gap * (len(rows) - 1)) / len(rows)
        for row_number, row in enumerate(rows):
            col = 0
            for index in row:
                width = cell_w * spans[index] + gap * (spans[index] - 1)
                boxes.append(
                    (
                        children[index],
                        inner_x + col * (cell_w + gap),
                        inner_y + row_number * (cell_h + gap),
                        width,
                        cell_h,
                    )
                )
                col += spans[index]
    out: list[dict[str, Any]] = []
    for number, (child, cx, cy, cw, ch) in enumerate(boxes, start=1):
        placed = _clean(child)
        placed.update({"x": round(cx, 3), "y": round(cy, 3), "w": round(cw, 3), "h": round(ch, 3)})
        if placed.get("type") in CONTAINERS:
            out.extend(_expand_container(placed, depth + 1, f"{where} > child {number}"))
        else:
            out.append(placed)
    return out


def expand_elements(elements: list[Any], slide_number: int) -> list[Any]:
    """The elements with every container and diagram replaced by the placed elements it describes (drawing order is kept),
    and the `align` and `distribute` instructions applied to the elements they name."""
    out: list[Any] = []
    arrangements: list[tuple[int, dict[str, Any]]] = []
    for number, element in enumerate(elements, start=1):
        where = f"slide {slide_number}, element {number}"
        if isinstance(element, dict) and element.get("type") in CONTAINERS:
            out.extend(_expand_container(element, 1, f"{where} ({element['type']})"))
        elif isinstance(element, dict) and element.get("type") == "diagram":
            try:
                out.extend(expand_diagram(element, f"{where} (diagram)", number))
            except DiagramError as error:
                raise LayoutError(str(error)) from error
        elif isinstance(element, dict) and element.get("type") in ("align", "distribute"):
            arrangements.append((number, element))
        else:
            out.append(element)
    for number, instruction in arrangements:
        _arrange(out, instruction, f"slide {slide_number}, element {number} ({instruction['type']})")
    return out


def _arrange(elements: list[Any], instruction: dict[str, Any], where: str) -> None:
    """Moves the elements named in `ids` so they line up (`align` to) or are evenly spaced (`distribute` axis)."""
    ids = instruction.get("ids")
    if not isinstance(ids, list) or len(ids) < 2:
        raise LayoutError(f"{where}: needs `ids`, a list of at least two element ids")
    by_id = {e.get("id"): e for e in elements if isinstance(e, dict) and e.get("id")}
    members = []
    for identifier in ids:
        found = by_id.get(identifier)
        if found is None or not all(isinstance(found.get(k), int | float) for k in ("x", "y", "w", "h")):
            raise LayoutError(
                f"{where}: no placed element with id {identifier!r} on this slide (give it an `id` and a position)"
            )
        members.append(found)
    if instruction["type"] == "align":
        mode = instruction.get("to")
        if mode not in ("left", "center", "right", "top", "middle", "bottom"):
            raise LayoutError(f"{where}: `to` must be left, center, right, top, middle or bottom")
        left, top = min(m["x"] for m in members), min(m["y"] for m in members)
        right, bottom = max(m["x"] + m["w"] for m in members), max(m["y"] + m["h"] for m in members)
        for m in members:
            if mode == "left":
                m["x"] = left
            elif mode == "right":
                m["x"] = round(right - m["w"], 3)
            elif mode == "center":
                m["x"] = round((left + right) / 2 - m["w"] / 2, 3)
            elif mode == "top":
                m["y"] = top
            elif mode == "bottom":
                m["y"] = round(bottom - m["h"], 3)
            else:
                m["y"] = round((top + bottom) / 2 - m["h"] / 2, 3)
        return
    if len(members) < 3:
        raise LayoutError(f"{where}: distribute needs at least three elements")
    axis = instruction.get("axis")
    if axis not in ("horizontal", "vertical"):
        raise LayoutError(f"{where}: `axis` must be horizontal or vertical")
    start_key, size_key = ("x", "w") if axis == "horizontal" else ("y", "h")
    members.sort(key=lambda m: m[start_key])
    span = members[-1][start_key] + members[-1][size_key] - members[0][start_key]
    gap = (span - sum(m[size_key] for m in members)) / (len(members) - 1)
    cursor = members[0][start_key]
    for m in members:
        m[start_key] = round(cursor, 3)
        cursor += m[size_key] + gap


def expand_layouts(deck: dict[str, Any]) -> dict[str, Any]:
    """Expands the containers of every freeform slide of a raw outline (a dict), in place, and returns it."""
    slides = deck.get("slides")
    if not isinstance(slides, list):
        return deck
    for number, slide in enumerate(slides, start=1):
        if (
            isinstance(slide, dict)
            and slide.get("layout") == "freeform"
            and isinstance(slide.get("elements"), list)
        ):
            slide["elements"] = expand_elements(slide["elements"], number)
    return deck
