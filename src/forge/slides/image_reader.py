"""A design shown as a picture of a slide (TODO P2.25, D-337): measured, not guessed.

`analyze_reference_image` takes a screenshot or a photo of a slide and reports what pixels can say: the dominant colours with their shares
(median-cut quantisation), the background colour and whether the slide is dark or light, the accent colours (the colourful ones), the
text colour, where the content sits (a coarse grid of edge density turned into regions, in percent of the slide and in inches on a
13.33 x 7.5 canvas), the marks in the corners (logos), and a brand kit for the outline. Fonts and photographs cannot be read from
pixels: the report says so and the model decides with `view_image`.

`compare_to_reference` scores a rendered slide against the reference: a colour distance per cell of an 8 x 5 grid (CIE76 on Lab) and the
palette match, so the model can fix the worst cells and try again (at most three rounds)."""

from __future__ import annotations

import io
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from forge.slides.colorvision import _rgb, delta

CANVAS = (13.333, 7.5)
GRID = (16, 9)  # cells for the layout regions
SCORE_GRID = (8, 5)
EDGE_THRESHOLD = 28.0  # mean edge strength (0-255) above which a cell holds content
MIN_SHARE = 0.01  # a palette colour must cover this share
SATURATED = 0.35
CORNER = 0.14  # the corner regions are this share of the width and height


@dataclass
class Region:
    x: float  # percent of the slide
    y: float
    w: float
    h: float
    density: float

    def inches(self) -> dict[str, float]:
        return {
            "x": round(self.x / 100 * CANVAS[0], 2),
            "y": round(self.y / 100 * CANVAS[1], 2),
            "w": round(self.w / 100 * CANVAS[0], 2),
            "h": round(self.h / 100 * CANVAS[1], 2),
        }


@dataclass
class ReferenceDesign:
    width: int
    height: int
    palette: list[tuple[str, float]] = field(default_factory=list)  # hex and share
    background: str = ""
    text_colour: str = ""
    accents: list[str] = field(default_factory=list)
    dark: bool = False
    regions: list[Region] = field(default_factory=list)
    corners: dict[str, bool] = field(default_factory=dict)
    brand: dict[str, str] = field(default_factory=dict)
    cannot_read: list[str] = field(
        default_factory=lambda: [
            "font families (guess from the picture with view_image)",
            "photographs and logos (ask the user for the files)",
        ]
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "picture_px": [self.width, self.height],
            "palette": self.palette,
            "background": self.background,
            "text_colour": self.text_colour,
            "accents": self.accents,
            "dark": self.dark,
            "regions": [
                {
                    "percent": [round(r.x, 1), round(r.y, 1), round(r.w, 1), round(r.h, 1)],
                    "inches": r.inches(),
                    "density": round(r.density, 2),
                }
                for r in self.regions
            ],
            "corners": self.corners,
            "brand": self.brand,
            "cannot_read": self.cannot_read,
        }


def _distance(first: str, second: str) -> float:
    """Colour difference (CIE76 on Lab) between two #RRGGBB colours."""
    return delta(_rgb(first), _rgb(second))


def _channels(value: str) -> tuple[int, int, int]:
    return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _saturation(rgb: tuple[int, int, int]) -> float:
    high, low = max(rgb), min(rgb)
    return 0.0 if high == 0 else (high - low) / high


def _open(data: bytes) -> Any:
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(data)) as image:
        picture = ImageOps.exif_transpose(image).convert("RGB")
    picture.load()
    return picture


def _palette(picture: Any) -> list[tuple[str, float]]:
    from PIL import Image

    small = picture.copy()
    small.thumbnail((240, 240))
    quantised = small.quantize(colors=10, method=Image.Quantize.MEDIANCUT)
    palette = quantised.getpalette() or []
    counts = sorted(quantised.getcolors() or [], reverse=True)
    total = sum(c for c, _ in counts) or 1
    out = []
    for count, index in counts:
        rgb = (palette[index * 3], palette[index * 3 + 1], palette[index * 3 + 2])
        if count / total >= MIN_SHARE:
            out.append((_hex(rgb), round(count / total, 3)))
    return out


def _border_colour(picture: Any) -> tuple[int, int, int]:
    """The commonest colour on the outer rim: the background (a title or logo rarely fills the whole rim)."""
    from collections import Counter

    width, height = picture.size
    small = picture.resize((64, 36))
    rim = [small.getpixel((x, y)) for x in range(64) for y in (0, 1, 34, 35)] + [
        small.getpixel((x, y)) for y in range(36) for x in (0, 1, 62, 63)
    ]
    quantised = Counter((r // 16 * 16 + 8, g // 16 * 16 + 8, b // 16 * 16 + 8) for r, g, b in rim)
    del width, height
    return quantised.most_common(1)[0][0]


def _regions(picture: Any, background: tuple[int, int, int]) -> tuple[list[Region], dict[str, bool]]:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

    columns, rows = GRID
    small = picture.resize((columns * 16, rows * 16))
    edges = small.convert("L").filter(ImageFilter.FIND_EDGES)
    ImageDraw.Draw(edges).rectangle(
        (0, 0, edges.width - 1, edges.height - 1), outline=0
    )  # the filter leaves the rim unfiltered: not an edge
    flat = ImageChops.difference(small, Image.new("RGB", small.size, background)).convert(
        "L"
    )  # distance from the background
    density = [[0.0] * columns for _ in range(rows)]
    for row in range(rows):
        for column in range(columns):
            box = (column * 16, row * 16, column * 16 + 16, row * 16 + 16)
            edge = edges.crop(box)
            away = flat.crop(box)
            e = ImageStat.Stat(edge).mean[0]
            a = ImageStat.Stat(away.point(lambda v: 255 if v > 40 else 0)).mean[0] / 255
            density[row][column] = max(e / EDGE_THRESHOLD, a)
    busy = [[density[r][c] >= 0.5 for c in range(columns)] for r in range(rows)]
    seen = [[False] * columns for _ in range(rows)]
    regions: list[Region] = []
    for r in range(rows):
        for c in range(columns):
            if not busy[r][c] or seen[r][c]:
                continue
            queue, cells = deque([(r, c)]), []
            seen[r][c] = True
            while queue:
                y, x = queue.popleft()
                cells.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < rows and 0 <= nx < columns and busy[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        queue.append((ny, nx))
            ys, xs = [y for y, _ in cells], [x for _, x in cells]
            mean = sum(min(density[y][x], 2.0) for y, x in cells) / len(cells)
            regions.append(
                Region(
                    min(xs) / columns * 100,
                    min(ys) / rows * 100,
                    (max(xs) - min(xs) + 1) / columns * 100,
                    (max(ys) - min(ys) + 1) / rows * 100,
                    mean,
                )
            )
    regions.sort(key=lambda g: (round(g.y / 10), g.x))
    corners = {
        name: any(
            g.x < (CORNER * 100 if "left" in name else 100)
            and g.x + g.w > (0 if "left" in name else 100 - CORNER * 100)
            and g.y < (CORNER * 100 if "top" in name else 100)
            and g.y + g.h > (0 if "top" in name else 100 - CORNER * 100)
            and g.w <= 30
            and g.h <= 25
            for g in regions
        )
        for name in ("top_left", "top_right", "bottom_left", "bottom_right")
    }
    return regions[:12], corners


def analyze_reference_image(data: bytes) -> ReferenceDesign:
    picture = _open(data)
    width, height = picture.size
    background_rgb = _border_colour(picture)
    palette = _palette(picture)
    # the palette entry closest to the rim colour is the background (the rim is quantised more coarsely)
    background = (
        min(palette, key=lambda p: _distance(p[0], _hex(background_rgb)))[0]
        if palette
        else _hex(background_rgb)
    )
    background_tuple = _channels(background)
    luminance = 0.299 * background_tuple[0] + 0.587 * background_tuple[1] + 0.114 * background_tuple[2]
    dark = luminance < 128
    others = [(c, s) for c, s in palette if _distance(c, background) > 12]
    accents = [c for c, _ in others if _saturation(_channels(c)) >= SATURATED][:4]
    neutral = [c for c, _ in others if c not in accents]
    text = next(
        (c for c in neutral if (sum(_channels(c)) / 3 > 128) == dark),
        "#FFFFFF" if dark else "#111111",
    )
    regions, corners = _regions(picture, background_tuple)
    brand: dict[str, str] = {"background": background, "text": text}
    if accents:
        brand["accent"] = accents[0]
    return ReferenceDesign(width, height, palette, background, text, accents, dark, regions, corners, brand)


def describe_reference(design: ReferenceDesign, name: str = "the picture") -> str:
    lines = [
        f"Design read from {name} ({design.width} x {design.height} px): a {'dark' if design.dark else 'light'} slide, background {design.background}, "
        f"text {design.text_colour}, accents {', '.join(design.accents) or 'none (greys only)'}.",
        "colours by share: " + ", ".join(f"{c} {int(s * 100)}%" for c, s in design.palette[:8]),
    ]
    if design.regions:
        lines.append(
            "content regions (x, y, w, h in inches on a 13.33 x 7.5 slide, top to bottom): "
            + "; ".join("({x:g}, {y:g}, {w:g} x {h:g})".format(**r.inches()) for r in design.regions)
        )
    marks = [name.replace("_", " ") for name, found in design.corners.items() if found]
    if marks:
        lines.append("marks in the corners (logos): " + ", ".join(marks))
    import json

    lines.append("brand kit to use in an outline: " + json.dumps(design.brand))
    lines.append("Cannot be read from pixels: " + "; ".join(design.cannot_read) + ".")
    return "\n".join(lines)


@dataclass
class Comparison:
    score: float  # 0 to 100, 100 = the same
    worst: list[tuple[int, int, float]] = field(
        default_factory=list
    )  # (column, row, distance) of the cells that differ most
    palette_match: float = 0.0  # share of the reference's colours that the slide has


def compare_to_reference(rendered: bytes, reference: bytes) -> Comparison:
    """How close a rendered slide is to the reference picture, in colour and layout (not in text or fonts)."""
    first, second = _open(rendered), _open(reference)
    columns, rows = SCORE_GRID
    a = first.resize((columns * 8, rows * 8))
    b = second.resize((columns * 8, rows * 8))
    cells: list[tuple[int, int, float]] = []
    for row in range(rows):
        for column in range(columns):
            box = (column * 8, row * 8, column * 8 + 8, row * 8 + 8)
            mean_a = a.crop(box).resize((1, 1)).getpixel((0, 0))
            mean_b = b.crop(box).resize((1, 1)).getpixel((0, 0))
            cells.append((column, row, _distance(_hex(mean_a), _hex(mean_b))))
    average = sum(d for _, _, d in cells) / len(cells)
    score = max(
        0.0, 100.0 - average * 1.6
    )  # a mean Lab distance of about 60 (black against white) scores near 0
    ours = [c for c, _ in _palette(first)]
    wanted = [c for c, s in _palette(second) if s >= 0.03]
    matched = (
        sum(1 for c in wanted if any(_distance(c, o) < 20 for o in ours)) / len(wanted) if wanted else 1.0
    )
    worst = sorted(cells, key=lambda cell: -cell[2])[:4]
    return Comparison(round(score, 1), [(c, r, round(d, 1)) for c, r, d in worst if d > 8], round(matched, 2))


def describe_comparison(result: Comparison) -> str:
    lines = [
        f"Match with the reference: {result.score:g} of 100 (colours and layout only); {int(result.palette_match * 100)}% of the reference's colours appear."
    ]
    if result.worst:
        lines.append(
            "Cells that differ most (column, row on an 8 x 5 grid, 1 = left/top): "
            + "; ".join(f"({c + 1}, {r + 1}) off by {d:g}" for c, r, d in result.worst)
        )
    lines.append(
        "Aim for 80 or more; look at both pictures with view_image for what the numbers cannot say (fonts, photos, spacing)."
    )
    return "\n".join(lines)
