"""Free-form slides (D-242): the model places every element itself, in inches, on the 13.333 x 7.5 canvas.

Freedom with guard rails. Because nothing is laid out for the model, the builder checks what a designer would
check by eye and names every problem by slide and element: an element outside the slide, text too close to the
edge, two elements colliding, text that does not fit its box (it shrinks first), text too small, text with too
little contrast against what is behind it, a picture without alt text."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from forge.slides import fit
from forge.slides.spec import (
    ChartElement,
    FreeformSlide,
    ImageElement,
    LineElement,
    ShapeElement,
    TableElement,
    TextElement,
)
from forge.slides.themes import Theme

WIDTH, HEIGHT = 13.333, 7.5
EDGE_TOLERANCE = 0.05  # an element may sit this far outside the slide before it is called out
TEXT_EDGE_MARGIN = 0.3  # unfilled text closer than this to an edge looks cramped
OVERLAP_AREA = 0.03  # square inches of overlap that count as a collision
SHAPES = {
    "rect": "RECTANGLE",
    "rounded": "ROUNDED_RECTANGLE",
    "oval": "OVAL",
    "triangle": "ISOSCELES_TRIANGLE",
    "diamond": "DIAMOND",
    "chevron": "CHEVRON",
    "pentagon": "PENTAGON",
    "arrow_right": "RIGHT_ARROW",
    "plus": "CROSS",
}


@dataclass
class Placed:
    """What the checks need to know about one drawn element."""

    index: int
    label: str
    x: float
    y: float
    w: float
    h: float
    fill: str | None = None  # the colour behind anything drawn inside it
    text_colour: str | None = None
    text_size: float = 0
    bold: bool = False
    has_text: bool = False
    is_line: bool = False

    def contains(self, other: Placed, slack: float = 0.05) -> bool:
        return (
            self.x - slack <= other.x
            and self.y - slack <= other.y
            and self.x + self.w + slack >= other.x + other.w
            and self.y + self.h + slack >= other.y + other.h
        )

    def overlap_area(self, other: Placed) -> float:
        width = min(self.x + self.w, other.x + other.w) - max(self.x, other.x)
        height = min(self.y + self.h, other.y + other.h) - max(self.y, other.y)
        return max(width, 0) * max(height, 0)


def resolve(theme: Theme, token: str) -> str:
    """The hex colour (no '#') for a theme colour name or a '#RRGGBB' value."""
    if token.startswith("#"):
        return token[1:].upper()
    if token.startswith("series"):
        return theme.palette[(int(token[6:]) - 1) % len(theme.palette)]
    return str(getattr(theme, token))


def _luminance(hex_colour: str) -> float:
    channels = []
    for start in (0, 2, 4):
        value = int(hex_colour[start : start + 2], 16) / 255
        channels.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(first: str, second: str) -> float:
    """WCAG contrast ratio between two hex colours (1 to 21)."""
    light, dark = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


class _Freeform:
    def __init__(self, builder: Any, spec: FreeformSlide) -> None:
        self.b, self.spec, self.theme = builder, spec, builder.theme
        self.placed: list[Placed] = []
        self.background = resolve(self.theme, spec.background) if spec.background else self.theme.background

    def name(self, index: int, element: Any) -> str:
        detail = getattr(element, "text", "") or getattr(element, "path", "") or getattr(element, "shape", "")
        return f"element {index} ({element.type}{': ' + detail[:30] if detail else ''})"

    # --- the elements ---

    def text(self, slide: Any, index: int, el: TextElement) -> None:
        b, theme = self.b, self.theme
        pad = el.pad if el.pad is not None else (0.15 if (el.fill or el.line) else 0.0)
        label = self.name(index, el)
        if el.fill or el.line:
            shape = b.rectangle(
                slide, el.x, el.y, el.w, el.h, resolve(theme, el.fill or "background"), el.rounded
            )
            if not el.fill:
                shape.fill.background()
            if el.line:
                shape.line.color.rgb = b.colour(resolve(theme, el.line))
                shape.line.width = b.m["pt"](1.5)
            frame = shape.text_frame
            frame.word_wrap = True
        else:
            frame = b.textbox(slide, el.x, el.y, el.w, el.h)
        frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = b.m["inches"](pad)
        frame.vertical_anchor = {
            "top": b.m["anchor"].TOP,
            "middle": b.m["anchor"].MIDDLE,
            "bottom": b.m["anchor"].BOTTOM,
        }[el.valign]
        lines = el.text.split("\n")
        size = el.size
        gap = 0.3 if el.bullets else 0.1  # space between paragraphs, as a share of the text size
        if el.autofit:
            texts = [(line, 1.0, el.bold) for line in lines]
            inner_w = el.w - 2 * pad - (0.3 if el.bullets else 0)
            size, fits = fit.fit_size(
                texts, inner_w, el.h - 2 * pad, el.size, el.min_size, gap_pt=el.size * gap
            )
            if not fits:
                b.warn(
                    f"{label}: the text does not fit its box even at {el.min_size:g} pt: "
                    "enlarge the box or cut words"
                )
        if size < 12:
            b.warn(f"{label}: {size:g} pt text is too small to read in a presentation")
        colour = resolve(theme, el.color)
        for number, line in enumerate(lines):
            b.paragraph(
                frame,
                number == 0,
                line,
                size,
                colour,
                bold=el.bold,
                italic=el.italic,
                heading=el.font == "title",
                font="Consolas" if el.font == "mono" else None,
                align=el.align,
                bullet=el.bullets,
                after=size * gap,
            )
        self.placed.append(
            Placed(
                index,
                label,
                el.x,
                el.y,
                el.w,
                el.h,
                fill=resolve(theme, el.fill) if el.fill else None,
                text_colour=colour,
                text_size=size,
                bold=el.bold,
                has_text=bool(el.text.strip()),
            )
        )

    def shape(self, slide: Any, index: int, el: ShapeElement) -> None:
        b, theme = self.b, self.theme
        kind = getattr(b.m["shape"], SHAPES[el.shape])
        shape = slide.shapes.add_shape(kind, *(b.m["inches"](v) for v in (el.x, el.y, el.w, el.h)))
        shape.shadow.inherit = False
        if el.fill:
            shape.fill.solid()
            shape.fill.fore_color.rgb = b.colour(resolve(theme, el.fill))
        else:
            shape.fill.background()
        if el.line:
            shape.line.color.rgb = b.colour(resolve(theme, el.line))
            shape.line.width = b.m["pt"](el.line_width)
        else:
            shape.line.fill.background()
        if el.rotate:
            shape.rotation = el.rotate
        label = self.name(index, el)
        colour = resolve(theme, el.color)
        if el.text:
            frame = shape.text_frame
            frame.word_wrap = True
            frame.margin_left = frame.margin_right = b.m["inches"](0.1)
            frame.vertical_anchor = {
                "top": b.m["anchor"].TOP,
                "middle": b.m["anchor"].MIDDLE,
                "bottom": b.m["anchor"].BOTTOM,
            }[el.valign]
            size, fits = fit.fit_size([(el.text, 1.0, el.bold)], el.w - 0.3, el.h - 0.1, el.size, 12)
            if not fits:
                b.warn(f"{label}: the label does not fit inside the shape: enlarge it or shorten the label")
            for number, line in enumerate(el.text.split("\n")):
                b.paragraph(
                    frame,
                    number == 0,
                    line,
                    size,
                    colour,
                    bold=el.bold,
                    heading=el.font == "title",
                    font="Consolas" if el.font == "mono" else None,
                    align=el.align,
                )
        else:
            size = 0
        self.placed.append(
            Placed(
                index,
                label,
                el.x,
                el.y,
                el.w,
                el.h,
                fill=resolve(theme, el.fill) if el.fill else None,
                text_colour=colour if el.text else None,
                text_size=size,
                bold=el.bold,
                has_text=bool(el.text),
            )
        )

    def line(self, slide: Any, index: int, el: LineElement) -> None:
        b = self.b
        connector = slide.shapes.add_connector(
            b.m["connector"].STRAIGHT, *(b.m["inches"](v) for v in (el.x1, el.y1, el.x2, el.y2))
        )
        connector.line.color.rgb = b.colour(resolve(self.theme, el.color))
        connector.line.width = b.m["pt"](el.width)
        if el.dash:
            connector.line.dash_style = b.m["line_style"].DASH
        if el.arrow:
            outline = connector.line._get_or_add_ln()
            outline.append(outline.makeelement(b.m["qn"]("a:tailEnd"), {"type": "triangle"}))
        self.placed.append(
            Placed(
                index,
                self.name(index, el),
                min(el.x1, el.x2),
                min(el.y1, el.y2),
                abs(el.x2 - el.x1),
                abs(el.y2 - el.y1),
                is_line=True,
            )
        )

    def image(self, slide: Any, index: int, el: ImageElement) -> None:
        from PIL import Image

        b = self.b
        data = b.read_image(el.path)
        with Image.open(io.BytesIO(data)) as picture:
            ratio = picture.width / picture.height
        box_ratio = el.w / el.h
        x, y, w, h = el.x, el.y, el.w, el.h
        if el.fit == "contain":
            w, h = (el.w, el.w / ratio) if ratio <= 0 or el.w / ratio <= el.h else (el.h * ratio, el.h)
            x, y = el.x + (el.w - w) / 2, el.y + (el.h - h) / 2
        shape = b.add_picture(slide, data, x, y, w, h, el.alt or "")
        if el.fit == "cover":  # fill the box and crop what spills over, evenly
            if ratio > box_ratio:
                shape.crop_left = shape.crop_right = (1 - box_ratio / ratio) / 2
            else:
                shape.crop_top = shape.crop_bottom = (1 - ratio / box_ratio) / 2
        label = self.name(index, el)
        if not el.alt:
            b.warn(f"{label}: the picture has no alt text: say what it shows")
        self.placed.append(Placed(index, label, x, y, w, h))

    def chart(self, slide: Any, index: int, el: ChartElement) -> None:
        self.b.add_chart(
            slide,
            el.kind,
            el.categories,
            el.series,
            (el.x, el.y, el.w, el.h),
            el.alt or f"{el.kind} chart",
            14,
        )
        self.placed.append(Placed(index, self.name(index, el), el.x, el.y, el.w, el.h))

    def table(self, slide: Any, index: int, el: TableElement) -> None:
        self.b.add_table(slide, el.columns, el.rows, (el.x, el.y, el.w, el.h), el.alt or "table", el.size)
        self.placed.append(Placed(index, self.name(index, el), el.x, el.y, el.w, el.h))

    # --- the checks a designer does by eye ---

    def check(self) -> None:
        warn = self.b.warn
        for item in self.placed:
            outside = max(-item.x, -item.y, item.x + item.w - WIDTH, item.y + item.h - HEIGHT)
            if outside > EDGE_TOLERANCE and not item.is_line:
                warn(f"{item.label}: extends {outside:.1f} in beyond the slide")
            elif item.has_text and item.fill is None and not item.is_line:
                near = min(item.x, item.y, WIDTH - item.x - item.w, HEIGHT - item.y - item.h)
                if near < TEXT_EDGE_MARGIN:
                    warn(
                        f"{item.label}: text sits only {max(near, 0):.1f} in from the slide edge: "
                        f"keep {TEXT_EDGE_MARGIN} in clear"
                    )
        solid = [p for p in self.placed if not p.is_line]
        for first_index, first in enumerate(solid):
            for second in solid[first_index + 1 :]:
                if first.overlap_area(second) > OVERLAP_AREA and not (
                    first.contains(second) or second.contains(first)
                ):
                    warn(f"{second.label} overlaps {first.label}: move or resize one of them")
        for number, item in enumerate(self.placed):
            if not (item.has_text and item.text_colour):
                continue
            behind = item.fill or next(
                (p.fill for p in reversed(self.placed[:number]) if p.fill and p.contains(item)),
                self.background,
            )
            ratio = contrast(item.text_colour, behind)
            large = item.text_size >= 24 or (item.bold and item.text_size >= 18.66)
            if ratio < (3.0 if large else 4.5):
                warn(f"{item.label}: low contrast ({ratio:.1f}:1) between the text and what is behind it")


def build_freeform(builder: Any, spec: FreeformSlide) -> None:
    form = _Freeform(builder, spec)
    slide = builder.new_slide("freeform", spec.title, spec.notes, form.background)
    box = spec.title_box
    title_colour = resolve(form.theme, box.color)
    if spec.title_visible:
        builder.title(
            slide,
            spec.title,
            box.size,
            title_colour,
            x=box.x,
            y=box.y,
            w=box.w,
            h=box.h,
            align=box.align,
            anchor=box.valign,
        )
        form.placed.append(
            Placed(
                0,
                "the title",
                box.x,
                box.y,
                box.w,
                box.h,
                text_colour=title_colour,
                text_size=box.size,
                bold=True,
                has_text=True,
            )
        )
    else:  # the title stays for navigation and screen readers, parked above the slide
        builder.title(slide, spec.title, 24, title_colour, x=0.8, y=-1.5, w=11.7, h=1.0)
    for index, element in enumerate(spec.elements, start=1):
        if isinstance(element, TextElement):
            form.text(slide, index, element)
        elif isinstance(element, ShapeElement):
            form.shape(slide, index, element)
        elif isinstance(element, LineElement):
            form.line(slide, index, element)
        elif isinstance(element, ImageElement):
            form.image(slide, index, element)
        elif isinstance(element, ChartElement):
            form.chart(slide, index, element)
        else:
            form.table(slide, index, element)
    if spec.footer:
        builder.add_footer(slide)
    form.check()
