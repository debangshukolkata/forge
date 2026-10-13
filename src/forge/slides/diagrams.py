"""Diagram recipes for freeform slides (TODO P2.6, D-286). A recipe states the idea and the items and returns ordinary elements
(rounded boxes, text, shapes and glued connectors with ids), so everything stays editable and goes through the same checks:

    {"type": "diagram", "recipe": "process", "x": 0.8, "y": 2.2, "w": 11.7, "h": 3, "items": ["Plan", "Build", "Ship"]}

Recipes: process, cycle, hierarchy, matrix (2 x 2), timeline, funnel, roadmap. Items are strings or objects with `title` and
optional `text` (and recipe-specific keys: `date` for a timeline, `children` for a hierarchy, `items` for a roadmap phase).
Common keys: `color` (a theme colour for the emphasis, default accent), `id` (a prefix for the generated ids, so connectors
and later `group`, `align` or `distribute` elements can refer to the parts)."""

from __future__ import annotations

import math
from typing import Any

RECIPES = ("process", "cycle", "hierarchy", "matrix", "timeline", "funnel", "roadmap")
MAX_ITEMS = {"process": 6, "cycle": 8, "matrix": 4, "timeline": 8, "funnel": 6, "roadmap": 5}


class DiagramError(ValueError):
    """A diagram cannot be laid out; the message says why."""


def _item(item: Any) -> dict[str, Any]:
    if isinstance(item, str):
        return {"title": item}
    if isinstance(item, dict) and "title" in item:
        return item
    raise DiagramError("every item needs a title: a string or an object with `title`")


def _label(item: dict[str, Any], size: float) -> str:
    text = f"**{item['title']}**"
    if item.get("text"):
        text += f"\n{item['text']}"
    return text


def _box(
    identifier: str, x: float, y: float, w: float, h: float, label: str, size: float, **style: Any
) -> dict[str, Any]:
    element = {
        "type": "text",
        "id": identifier,
        "x": round(x, 3),
        "y": round(y, 3),
        "w": round(w, 3),
        "h": round(h, 3),
        "text": label,
        "rich": True,
        "size": size,
        "fill": "surface",
        "rounded": True,
        "align": "center",
        "valign": "middle",
        "color": "text",
        "min_size": 11,
    }
    element.update(style)
    return element


def _connector(
    start: str,
    start_side: str,
    end: str,
    end_side: str,
    colour: str,
    kind: str = "straight",
    arrow: bool = True,
) -> dict[str, Any]:
    return {
        "type": "line",
        "start": {"id": start, "side": start_side},
        "end": {"id": end, "side": end_side},
        "kind": kind,
        "arrow": arrow,
        "color": colour,
        "width": 2.0,
    }


def _line(x1: float, y1: float, x2: float, y2: float, colour: str) -> dict[str, Any]:
    return {
        "type": "line",
        "x1": round(x1, 3),
        "y1": round(y1, 3),
        "x2": round(x2, 3),
        "y2": round(y2, 3),
        "color": colour,
        "width": 2.0,
    }


def _check_count(recipe: str, items: list[Any], low: int = 2) -> None:
    high = MAX_ITEMS.get(recipe, 99)
    if not low <= len(items) <= high:
        raise DiagramError(f"a {recipe} diagram needs {low} to {high} items, got {len(items)}")


def _process(
    prefix: str, x: float, y: float, w: float, h: float, items: list[dict[str, Any]], colour: str
) -> list[dict[str, Any]]:
    _check_count("process", items)
    gap = 0.6
    box_w = (w - gap * (len(items) - 1)) / len(items)
    size = 20 if len(items) <= 4 else 17
    out: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        label = _label({**item, "title": f"{index + 1}  {item['title']}"}, size)
        out.append(_box(f"{prefix}-{index + 1}", x + index * (box_w + gap), y, box_w, h, label, size))
    out += [
        _connector(f"{prefix}-{i}", "right", f"{prefix}-{i + 1}", "left", colour)
        for i in range(1, len(items))
    ]
    return out


def _cycle(
    prefix: str, x: float, y: float, w: float, h: float, items: list[dict[str, Any]], colour: str, center: str
) -> list[dict[str, Any]]:
    _check_count("cycle", items, 3)
    node_w, node_h = min(w * 0.28, 2.9), min(h * 0.2, 1.1)
    cx, cy = x + w / 2, y + h / 2
    rx, ry = (w - node_w) / 2, (h - node_h) / 2
    out: list[dict[str, Any]] = []
    centres = []
    for index, item in enumerate(items):
        angle = -math.pi / 2 + 2 * math.pi * index / len(items)
        px, py = cx + rx * math.cos(angle), cy + ry * math.sin(angle)
        centres.append((px, py))
        out.append(
            _box(
                f"{prefix}-{index + 1}",
                px - node_w / 2,
                py - node_h / 2,
                node_w,
                node_h,
                _label(item, 18),
                18,
            )
        )
    for index in range(len(items)):
        (ax, ay), (bx, by) = centres[index], centres[(index + 1) % len(items)]
        if abs(bx - ax) >= abs(by - ay):
            sides = ("right", "left") if bx > ax else ("left", "right")
        else:
            sides = ("bottom", "top") if by > ay else ("top", "bottom")
        out.append(
            _connector(
                f"{prefix}-{index + 1}",
                sides[0],
                f"{prefix}-{(index + 1) % len(items) + 1}",
                sides[1],
                colour,
            )
        )
    if center:
        out.append(
            {
                "type": "shape",
                "id": f"{prefix}-center",
                "shape": "oval",
                "x": round(cx - 1.1, 3),
                "y": round(cy - 0.7, 3),
                "w": 2.2,
                "h": 1.4,
                "fill": colour,
                "text": center,
                "size": 18,
                "bold": True,
                "color": "accent_text",
            }
        )
    return out


def _hierarchy(
    prefix: str, x: float, y: float, w: float, h: float, items: list[dict[str, Any]], colour: str
) -> list[dict[str, Any]]:
    if len(items) != 1:
        raise DiagramError("a hierarchy diagram has one root item (put the rest in its `children`)")

    def depth(node: dict[str, Any]) -> int:
        return 1 + max((depth(_item(c)) for c in node.get("children", [])), default=0)

    def leaves(node: dict[str, Any]) -> int:
        kids = node.get("children", [])
        return sum(leaves(_item(c)) for c in kids) if kids else 1

    levels, total = depth(items[0]), leaves(items[0])
    slot = w / total
    gap_y = 0.55
    node_h = min(1.1, (h - gap_y * (levels - 1)) / levels)
    node_w = min(slot * 0.86, 2.8)
    out: list[dict[str, Any]] = []
    counter = [0]

    def place(node: dict[str, Any], level: int, left: float) -> tuple[float, str]:
        counter[0] += 1
        identifier = f"{prefix}-{counter[0]}"
        kids = [_item(c) for c in node.get("children", [])]
        if kids:
            cursor, centres = left, []
            for kid in kids:
                centre, kid_id = place(kid, level + 1, cursor)
                centres.append((centre, kid_id))
                cursor += leaves(kid) * slot
            centre = (centres[0][0] + centres[-1][0]) / 2
        else:
            centre, centres = left + slot / 2, []
        style: dict[str, Any] = {"fill": colour, "color": "accent_text"} if level == 0 else {}
        out.append(
            _box(
                identifier,
                centre - node_w / 2,
                y + level * (node_h + gap_y),
                node_w,
                node_h,
                _label(node, 17),
                17,
                **style,
            )
        )
        if centres:  # a bus: down from the parent, across, down into every child (plain lines: an elbow connector bends sideways first)
            parent_bottom = y + level * (node_h + gap_y) + node_h
            middle = parent_bottom + gap_y / 2
            child_top = y + (level + 1) * (node_h + gap_y)
            out.append(_line(centre, parent_bottom, centre, middle, colour))
            if len(centres) > 1:
                out.append(_line(centres[0][0], middle, centres[-1][0], middle, colour))
            out.extend(_line(c, middle, c, child_top, colour) for c, _ in centres)
        return centre, identifier

    place(items[0], 0, x)
    return out


def _matrix(
    prefix: str,
    x: float,
    y: float,
    w: float,
    h: float,
    items: list[dict[str, Any]],
    colour: str,
    spec: dict[str, Any],
) -> list[dict[str, Any]]:
    if len(items) != 4:
        raise DiagramError(
            "a matrix diagram needs exactly 4 items: top left, top right, bottom left, bottom right"
        )
    left, bottom, gap = 0.7, 0.55, 0.2
    cell_w, cell_h = (w - left - gap) / 2, (h - bottom - gap) / 2
    highlight = spec.get("highlight")
    out: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        column, row = index % 2, index // 2
        style = {"fill": colour, "color": "accent_text"} if highlight == index + 1 else {}
        out.append(
            _box(
                f"{prefix}-{index + 1}",
                x + left + column * (cell_w + gap),
                y + row * (cell_h + gap),
                cell_w,
                cell_h,
                _label(item, 18),
                18,
                **style,
            )
        )
    bottom_y = y + h - bottom + 0.12
    out.append(
        {
            "type": "line",
            "x1": round(x + left, 3),
            "y1": round(bottom_y, 3),
            "x2": round(x + w, 3),
            "y2": round(bottom_y, 3),
            "arrow": True,
            "color": "muted",
            "width": 2,
        }
    )
    out.append(
        {
            "type": "line",
            "x1": round(x + left - 0.12, 3),
            "y1": round(y + h - bottom, 3),
            "x2": round(x + left - 0.12, 3),
            "y2": round(y, 3),
            "arrow": True,
            "color": "muted",
            "width": 2,
        }
    )
    if spec.get("x_label"):
        out.append(
            {
                "type": "text",
                "x": round(x + left, 3),
                "y": round(bottom_y + 0.05, 3),
                "w": round(w - left, 3),
                "h": 0.38,
                "text": spec["x_label"],
                "size": 14,
                "color": "muted",
                "align": "center",
                "min_size": 11,
            }
        )
    if spec.get("y_label"):
        out.append(
            {
                "type": "text",
                "x": round(x - 0.1, 3),
                "y": round(y, 3),
                "w": 0.5,
                "h": round(h - bottom, 3),
                "text": spec["y_label"],
                "size": 14,
                "color": "muted",
                "align": "center",
                "valign": "middle",
                "vertical": "up",
                "min_size": 11,
            }
        )
    return out


def _timeline(
    prefix: str, x: float, y: float, w: float, h: float, items: list[dict[str, Any]], colour: str
) -> list[dict[str, Any]]:
    _check_count("timeline", items)
    mid = y + h / 2
    out: list[dict[str, Any]] = [
        {
            "type": "line",
            "x1": round(x, 3),
            "y1": round(mid, 3),
            "x2": round(x + w, 3),
            "y2": round(mid, 3),
            "color": "muted",
            "width": 3,
        }
    ]
    slot = w / len(items)
    label_w, label_h = min(slot * 1.7, 3.0), h / 2 - 0.35
    for index, item in enumerate(items):
        cx = x + slot * (index + 0.5)
        above = index % 2 == 0
        out.append(
            {
                "type": "shape",
                "id": f"{prefix}-{index + 1}",
                "shape": "oval",
                "x": round(cx - 0.16, 3),
                "y": round(mid - 0.16, 3),
                "w": 0.32,
                "h": 0.32,
                "fill": colour,
            }
        )
        title = f"**{item['title']}**"
        if item.get("date"):
            title = f"{{{colour}}}{item['date']}{{/}}\n{title}"
        if item.get("text"):
            title += f"\n{item['text']}"
        top = mid - 0.3 - label_h if above else mid + 0.3
        out.append(
            {
                "type": "text",
                "x": round(cx - label_w / 2, 3),
                "y": round(top, 3),
                "w": round(label_w, 3),
                "h": round(label_h, 3),
                "text": title,
                "rich": True,
                "size": 16,
                "align": "center",
                "valign": "bottom" if above else "top",
                "min_size": 11,
            }
        )
    return out


def _funnel(
    prefix: str, x: float, y: float, w: float, h: float, items: list[dict[str, Any]], colour: str
) -> list[dict[str, Any]]:
    _check_count("funnel", items)
    gap = 0.12
    bar_h = (h - gap * (len(items) - 1)) / len(items)
    out: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        share = 1 - 0.65 * index / max(len(items) - 1, 1)
        bar_w = w * share
        opacity = 1.0 if index == 0 else round(0.62 - 0.32 * (index - 1) / max(len(items) - 2, 1), 2)
        light_text = index == 0  # white on the full colour, dark text on the lighter tints
        label = item["title"] + (f"  {item['text']}" if item.get("text") else "")
        out.append(
            {
                "type": "text",
                "id": f"{prefix}-{index + 1}",
                "x": round(x + (w - bar_w) / 2, 3),
                "y": round(y + index * (bar_h + gap), 3),
                "w": round(bar_w, 3),
                "h": round(bar_h, 3),
                "text": label,
                "size": 18,
                "bold": True,
                "fill": colour,
                "opacity": opacity,
                "rounded": True,
                "align": "center",
                "valign": "middle",
                "color": "accent_text" if light_text else "text",
                "min_size": 11,
            }
        )
    return out


def _roadmap(
    prefix: str, x: float, y: float, w: float, h: float, items: list[dict[str, Any]], colour: str
) -> list[dict[str, Any]]:
    _check_count("roadmap", items)
    gap = 0.2
    column_w = (w - gap * (len(items) - 1)) / len(items)
    head_h = 0.8
    out: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        left = x + index * (column_w + gap)
        out.append(
            {
                "type": "shape",
                "id": f"{prefix}-{index + 1}",
                "shape": "pentagon",
                "x": round(left, 3),
                "y": round(y, 3),
                "w": round(column_w, 3),
                "h": head_h,
                "fill": colour,
                "text": item["title"],
                "size": 18,
                "bold": True,
                "color": "accent_text",
            }
        )
        lines = [str(t) for t in item.get("items", [])] or ([item["text"]] if item.get("text") else [])
        if lines:
            out.append(
                {
                    "type": "text",
                    "id": f"{prefix}-{index + 1}-card",
                    "x": round(left, 3),
                    "y": round(y + head_h + 0.15, 3),
                    "w": round(column_w - 0.1, 3),
                    "h": round(min(h - head_h - 0.15, 0.55 + 0.42 * len(lines)), 3),
                    "text": "\n".join(lines),
                    "bullets": True,
                    "size": 16,
                    "fill": "surface",
                    "rounded": True,
                    "color": "text",
                    "min_size": 11,
                }
            )
    return out


def expand_diagram(node: dict[str, Any], where: str, number: int) -> list[dict[str, Any]]:
    """The elements of one diagram node (`{"type": "diagram", "recipe": ...}`)."""
    recipe = node.get("recipe")
    if recipe not in RECIPES:
        raise DiagramError(f"{where}: unknown recipe {recipe!r}; recipes are {', '.join(RECIPES)}")
    for key in ("x", "y", "w", "h"):
        if not isinstance(node.get(key), int | float):
            raise DiagramError(f"{where}: a diagram needs x, y, w and h (the box it fills)")
    items = node.get("items")
    if not isinstance(items, list) or not items:
        raise DiagramError(f"{where}: a diagram needs a non-empty `items` list")
    x, y, w, h = (float(node[k]) for k in ("x", "y", "w", "h"))
    prefix = str(node.get("id") or f"{recipe}{number}")
    colour = str(node.get("color", "accent"))
    try:
        parsed = [_item(item) for item in items]
        if recipe == "process":
            return _process(prefix, x, y, w, h, parsed, colour)
        if recipe == "cycle":
            return _cycle(prefix, x, y, w, h, parsed, colour, str(node.get("center", "")))
        if recipe == "hierarchy":
            return _hierarchy(prefix, x, y, w, h, parsed, colour)
        if recipe == "matrix":
            return _matrix(prefix, x, y, w, h, parsed, colour, node)
        if recipe == "timeline":
            return _timeline(prefix, x, y, w, h, parsed, colour)
        if recipe == "funnel":
            return _funnel(prefix, x, y, w, h, parsed, colour)
        return _roadmap(prefix, x, y, w, h, parsed, colour)
    except DiagramError as error:
        raise DiagramError(f"{where}: {error}") from error
