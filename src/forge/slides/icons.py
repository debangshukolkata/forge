"""Icons for slides (TODO P2.3, D-283): the bundled Lucide (ISC) and Material Symbols (Apache-2.0) icons turned into native
PowerPoint shapes, so they recolour, resize and edit like any shape and need no picture library. An icon is read from the
bundled data, its SVG paths are flattened to polylines (curves and arcs sampled finely), and the polylines are drawn as
freeform shapes in one group: Lucide icons as round-capped outlines (their design), Material Symbols as filled shapes.

Names: `lucide:rocket`, `material:rocket_launch`, or a bare name (Lucide first, then Material)."""

from __future__ import annotations

import gzip
import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

CURVE_STEPS = 14
ARC_STEP = math.pi / 18  # radians between sampled points on an arc
NUMBER = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
COMMAND = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]")
Point = tuple[float, float]


class IconError(ValueError):
    """The icon name is unknown or its drawing cannot be read; the message suggests alternatives."""


@dataclass(frozen=True)
class Contour:
    points: tuple[Point, ...]
    closed: bool


@dataclass(frozen=True)
class IconShape:
    """An icon ready to draw: contours in a unit square (0 to 1), and how to paint them."""

    name: str
    contours: tuple[Contour, ...]
    stroke: bool  # True: outline icon (Lucide); False: filled icon (Material)
    stroke_fraction: float  # line width as a share of the icon size (outline icons)


# --- the bundled data ---


@lru_cache(maxsize=2)
def _set(name: str) -> dict[str, Any]:
    data = resources.files("forge") / "data" / "icons" / f"{name}.json.gz"
    return json.loads(gzip.decompress(data.read_bytes()).decode("utf-8"))  # type: ignore[no-any-return]


def icon_names(library: str) -> list[str]:
    return sorted(_set(library)["icons"])


def search_icons(query: str, limit: int = 8) -> list[str]:
    """Icon names (`lucide:name` / `material:name`) best matching the words in `query`, by name and tag."""
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 1]
    words += [w[:-1] for w in words if w.endswith("s") and len(w) > 3]  # a plural also matches the singular
    scored: list[tuple[int, str]] = []
    for library in ("lucide", "material"):
        for name, entry in _set(library)["icons"].items():
            tags = entry.get("t", []) if isinstance(entry, dict) else []
            name_words = set(re.findall(r"[a-z0-9]+", name.replace("_", "-")))
            tag_words = {w for tag in tags for w in re.findall(r"[a-z0-9]+", tag.lower())}
            score = sum(
                3 * (w in name_words) + 2 * (w == name.replace("-", "").replace("_", "")) + (w in tag_words)
                for w in words
            )
            if score:
                scored.append((score, f"{library}:{name}"))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [name for _, name in scored[:limit]]


# --- path parsing and flattening ---


def _numbers(text: str) -> list[float]:
    return [float(m) for m in NUMBER.findall(text)]


def _arc_points(
    start: Point, rx: float, ry: float, rotation: float, large: bool, sweep: bool, end: Point
) -> list[Point]:
    """Points along an SVG elliptical arc from `start` to `end` (the end point is included)."""
    if rx == 0 or ry == 0 or start == end:
        return [end]
    rx, ry = abs(rx), abs(ry)
    phi = math.radians(rotation)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)
    dx, dy = (start[0] - end[0]) / 2, (start[1] - end[1]) / 2
    x1 = cos_phi * dx + sin_phi * dy
    y1 = -sin_phi * dx + cos_phi * dy
    scale = x1**2 / rx**2 + y1**2 / ry**2
    if scale > 1:  # the radii are too small to reach: scale them up
        rx, ry = rx * math.sqrt(scale), ry * math.sqrt(scale)
    numerator = rx**2 * ry**2 - rx**2 * y1**2 - ry**2 * x1**2
    denominator = rx**2 * y1**2 + ry**2 * x1**2
    factor = math.sqrt(max(0.0, numerator / denominator)) if denominator else 0.0
    if large == sweep:
        factor = -factor
    cx1, cy1 = factor * rx * y1 / ry, -factor * ry * x1 / rx
    cx = cos_phi * cx1 - sin_phi * cy1 + (start[0] + end[0]) / 2
    cy = sin_phi * cx1 + cos_phi * cy1 + (start[1] + end[1]) / 2

    def angle(ux: float, uy: float, vx: float, vy: float) -> float:
        value = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return value

    theta1 = angle(1, 0, (x1 - cx1) / rx, (y1 - cy1) / ry)
    delta = angle((x1 - cx1) / rx, (y1 - cy1) / ry, (-x1 - cx1) / rx, (-y1 - cy1) / ry)
    if not sweep and delta > 0:
        delta -= 2 * math.pi
    elif sweep and delta < 0:
        delta += 2 * math.pi
    steps = max(2, math.ceil(abs(delta) / ARC_STEP))
    points = []
    for step in range(1, steps + 1):
        theta = theta1 + delta * step / steps
        x = cos_phi * rx * math.cos(theta) - sin_phi * ry * math.sin(theta) + cx
        y = sin_phi * rx * math.cos(theta) + cos_phi * ry * math.sin(theta) + cy
        points.append((x, y))
    points[-1] = end
    return points


def _cubic(p0: Point, p1: Point, p2: Point, p3: Point) -> list[Point]:
    out = []
    for step in range(1, CURVE_STEPS + 1):
        t = step / CURVE_STEPS
        u = 1 - t
        out.append(
            (
                u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0],
                u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1],
            )
        )
    return out


def _quadratic(p0: Point, p1: Point, p2: Point) -> list[Point]:
    out = []
    for step in range(1, CURVE_STEPS + 1):
        t = step / CURVE_STEPS
        u = 1 - t
        out.append(
            (u**2 * p0[0] + 2 * u * t * p1[0] + t**2 * p2[0], u**2 * p0[1] + 2 * u * t * p1[1] + t**2 * p2[1])
        )
    return out


def parse_path(data: str) -> list[Contour]:
    """The contours of an SVG path `d` attribute (all commands, absolute and relative, arcs included)."""
    contours: list[Contour] = []
    current: list[Point] = []
    pos: Point = (0.0, 0.0)
    start: Point = (0.0, 0.0)
    last_control: Point | None = None
    last_command = ""
    cursor = 0
    command = ""

    def take_number() -> float:
        nonlocal cursor
        match = NUMBER.match(data, _skip(cursor))
        if match is None:
            raise IconError(f"cannot read a number in the path near {data[cursor : cursor + 12]!r}")
        cursor = match.end()
        return float(match.group())

    def take_flag() -> bool:
        nonlocal cursor
        cursor = _skip(cursor)
        flag = data[cursor : cursor + 1]
        if flag not in ("0", "1"):
            raise IconError("an arc flag must be 0 or 1")
        cursor += 1
        return flag == "1"

    def _skip(index: int) -> int:
        while index < len(data) and data[index] in " ,\t\r\n":
            index += 1
        return index

    def finish(closed: bool) -> None:
        nonlocal current
        if len(current) > 1:
            contours.append(Contour(tuple(current), closed))
        current = []

    while True:
        cursor = _skip(cursor)
        if cursor >= len(data):
            break
        if COMMAND.match(data[cursor]):
            command = data[cursor]
            cursor += 1
            if command in "Zz":
                if current:
                    current.append(start)
                    finish(True)
                pos = start
                last_control = None
                last_command = command
                continue
        elif not command:
            raise IconError("the path does not start with a command")
        relative = command.islower()
        base = pos if relative else (0.0, 0.0)
        kind = command.upper()
        if kind == "M":
            x, y = take_number(), take_number()
            pos = (base[0] + x, base[1] + y)
            finish(False)
            current = [pos]
            start = pos
            command = "l" if relative else "L"  # extra coordinate pairs after a move are line-tos
            last_control = None
        elif kind == "L":
            x, y = take_number(), take_number()
            pos = (base[0] + x, base[1] + y)
            current.append(pos)
            last_control = None
        elif kind == "H":
            x = take_number()
            pos = (base[0] + x if relative else x, pos[1])
            current.append(pos)
            last_control = None
        elif kind == "V":
            y = take_number()
            pos = (pos[0], base[1] + y if relative else y)
            current.append(pos)
            last_control = None
        elif kind == "C":
            nums = [take_number() for _ in range(6)]
            p1, p2, p3 = (
                (base[0] + nums[0], base[1] + nums[1]),
                (base[0] + nums[2], base[1] + nums[3]),
                (base[0] + nums[4], base[1] + nums[5]),
            )
            current.extend(_cubic(pos, p1, p2, p3))
            pos, last_control = p3, p2
        elif kind == "S":
            nums = [take_number() for _ in range(4)]
            reflected = (
                (2 * pos[0] - last_control[0], 2 * pos[1] - last_control[1])
                if last_control and last_command in "CcSs"
                else pos
            )
            p2, p3 = (base[0] + nums[0], base[1] + nums[1]), (base[0] + nums[2], base[1] + nums[3])
            current.extend(_cubic(pos, reflected, p2, p3))
            pos, last_control = p3, p2
        elif kind == "Q":
            nums = [take_number() for _ in range(4)]
            p1, p2 = (base[0] + nums[0], base[1] + nums[1]), (base[0] + nums[2], base[1] + nums[3])
            current.extend(_quadratic(pos, p1, p2))
            pos, last_control = p2, p1
        elif kind == "T":
            nums = [take_number() for _ in range(2)]
            p1 = (
                (2 * pos[0] - last_control[0], 2 * pos[1] - last_control[1])
                if last_control and last_command in "QqTt"
                else pos
            )
            p2 = (base[0] + nums[0], base[1] + nums[1])
            current.extend(_quadratic(pos, p1, p2))
            pos, last_control = p2, p1
        else:  # arc
            rx, ry, rotation = take_number(), take_number(), take_number()
            large, sweep = take_flag(), take_flag()
            x, y = take_number(), take_number()
            end = (base[0] + x, base[1] + y)
            current.extend(_arc_points(pos, rx, ry, rotation, large, sweep, end))
            pos, last_control = end, None
        last_command = command
    finish(False)
    return contours


def _ellipse(cx: float, cy: float, rx: float, ry: float) -> Contour:
    steps = 48
    return Contour(
        tuple(
            (cx + rx * math.cos(2 * math.pi * i / steps), cy + ry * math.sin(2 * math.pi * i / steps))
            for i in range(steps + 1)
        ),
        True,
    )


def _rect(x: float, y: float, w: float, h: float, rx: float, ry: float) -> Contour:
    rx, ry = min(rx or ry, w / 2), min(ry or rx, h / 2)
    if not rx and not ry:
        return Contour(((x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)), True)
    d = f"M{x + rx} {y}H{x + w - rx}A{rx} {ry} 0 0 1 {x + w} {y + ry}V{y + h - ry}A{rx} {ry} 0 0 1 {x + w - rx} {y + h}H{x + rx}A{rx} {ry} 0 0 1 {x} {y + h - ry}V{y + ry}A{rx} {ry} 0 0 1 {x + rx} {y}Z"
    return parse_path(d)[0]


def _element_contours(tag: str, attrs: dict[str, str]) -> list[Contour]:
    def number(name: str, default: float = 0.0) -> float:
        try:
            return float(attrs.get(name, default))
        except ValueError:
            return default

    if tag == "path":
        return parse_path(attrs.get("d", ""))
    if tag == "circle":
        return [_ellipse(number("cx"), number("cy"), number("r"), number("r"))]
    if tag == "ellipse":
        return [_ellipse(number("cx"), number("cy"), number("rx"), number("ry"))]
    if tag == "rect":
        return [
            _rect(number("x"), number("y"), number("width"), number("height"), number("rx"), number("ry"))
        ]
    if tag == "line":
        return [Contour(((number("x1"), number("y1")), (number("x2"), number("y2"))), False)]
    if tag in ("polyline", "polygon"):
        values = _numbers(attrs.get("points", ""))
        pairs = list(zip(values[0::2], values[1::2], strict=False))
        if tag == "polygon" and pairs:
            pairs.append(pairs[0])
        return [Contour(tuple(pairs), tag == "polygon")] if len(pairs) > 1 else []
    return []


def load_icon(name: str) -> IconShape:
    """The icon as contours in a unit square. Raises IconError (with similar names) when it does not exist."""
    library, _, bare = name.partition(":")
    if not bare:
        library, bare = "", name
    options = [library] if library else ["lucide", "material"]
    for lib in options:
        if lib not in ("lucide", "material"):
            raise IconError(f"unknown icon library '{lib}': use lucide or material")
        data = _set(lib)
        key = next(
            (k for k in (bare, bare.replace("-", "_"), bare.replace("_", "-")) if k in data["icons"]), None
        )
        if key is None:
            continue
        entry = data["icons"][key]
        min_x, min_y, width, height = data["viewBox"]
        if lib == "lucide":
            contours = [c for tag, attrs in entry["n"] for c in _element_contours(tag, attrs)]
        else:
            contours = parse_path(entry)
        scaled = tuple(
            Contour(tuple(((x - min_x) / width, (y - min_y) / height) for x, y in c.points), c.closed)
            for c in contours
        )
        stroke = data["style"] == "stroke"
        return IconShape(
            f"{lib}:{key}", scaled, stroke, data.get("strokeWidth", 2) / width if stroke else 0.0
        )
    similar = ", ".join(search_icons(bare.replace("_", " ").replace("-", " "), 5))
    raise IconError(
        f"no icon named '{name}'" + (f"; similar: {similar}" if similar else "; use find_icon to search")
    )
