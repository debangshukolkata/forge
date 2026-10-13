"""Free-form slides (D-242): the model places every element itself, in inches, on the 13.333 x 7.5 canvas.

Freedom with guard rails. Because nothing is laid out for the model, the builder checks what a designer would
check by eye and names every problem by slide and element: an element outside the slide, text too close to the
edge, two elements colliding, text that does not fit its box (it shrinks first), text too small, text with too
little contrast against what is behind it, a picture without alt text."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from forge.slides import effects, fit
from forge.slides.icons import IconError, load_icon
from forge.slides.richtext import parse_runs, plain_text
from forge.slides.spec import (
    ChartElement,
    FreeformSlide,
    IconElement,
    ImageElement,
    LineElement,
    ShapeElement,
    TableElement,
    TextElement,
)
from forge.slides.themes import Theme, mix

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
        self.backgrounds = [self.background]  # every colour text may sit on directly (a gradient has two)

    def layer_background(self, slide: Any) -> None:
        """A gradient and/or a full-bleed picture behind everything, with an optional scrim over the picture."""
        spec, b = self.spec, self.b
        if spec.background_to:
            last = resolve(self.theme, spec.background_to)
            layer = b.rectangle(slide, 0, 0, WIDTH, HEIGHT, self.background)
            effects.set_gradient(layer, self.background, last, spec.background_angle)
            effects.send_to_back(slide, layer)
            self.backgrounds = [self.background, last]
        if not spec.background_image:
            return
        from PIL import Image, ImageStat

        data = b.read_image(spec.background_image)
        with Image.open(io.BytesIO(data)) as picture:
            ratio = picture.width / picture.height
            average = "".join(f"{round(v):02X}" for v in ImageStat.Stat(picture.convert("RGB")).mean)
        cover = b.add_picture(slide, data, 0, 0, WIDTH, HEIGHT, "")
        box_ratio = WIDTH / HEIGHT
        if ratio > box_ratio:
            cover.crop_left = cover.crop_right = (1 - box_ratio / ratio) / 2
        else:
            cover.crop_top = cover.crop_bottom = (1 - ratio / box_ratio) / 2
        if spec.scrim > 0:
            veil = b.rectangle(slide, 0, 0, WIDTH, HEIGHT, self.background)
            effects.set_solid(veil, self.background, spec.scrim)
            effects.send_to_back(slide, veil)
        effects.send_to_back(slide, cover)
        self.backgrounds = [mix(average, self.background, spec.scrim)]  # about what the text sits on

    def apply_fill(
        self, shape: Any, fill: str | None, fill_to: str | None, angle: float, opacity: float, shadow: str
    ) -> list[str]:
        """Gradient, transparency and shadow on a shape; returns the colours text on it may sit over, as they look on the
        slide (a transparent fill is mixed with the background), so the contrast check stays honest."""
        if shadow != "none":
            effects.set_shadow(shape, shadow)
        if not fill:
            return []
        first = resolve(self.theme, fill)
        if fill_to:
            last = resolve(self.theme, fill_to)
            effects.set_gradient(shape, first, last, angle, opacity)
            colours = [first, last]
        else:
            if opacity < 1:
                effects.set_solid(shape, first, opacity)
            colours = [first]
        if opacity < 1:
            colours = [mix(c, self.background, 1 - opacity) for c in colours]
        return colours

    @staticmethod
    def worst_behind(text_colour: str, candidates: list[str]) -> str | None:
        """Of the colours behind some text, the one it reads worst against (None when there is no fill)."""
        return min(candidates, key=lambda c: contrast(text_colour, c)) if candidates else None

    def name(self, index: int, element: Any) -> str:
        detail = getattr(element, "text", "") or getattr(element, "path", "") or getattr(element, "shape", "")
        return f"element {index} ({element.type}{': ' + detail[:30] if detail else ''})"

    # --- the elements ---

    def text(self, slide: Any, index: int, el: TextElement) -> None:
        b, theme = self.b, self.theme
        pad = el.pad if el.pad is not None else (0.15 if (el.fill or el.line) else 0.0)
        label = self.name(index, el)
        candidates: list[str] = []
        if el.fill or el.line:
            shape = b.rectangle(
                slide, el.x, el.y, el.w, el.h, resolve(theme, el.fill or "background"), el.rounded
            )
            if not el.fill:
                shape.fill.background()
            if el.line:
                shape.line.color.rgb = b.colour(resolve(theme, el.line))
                shape.line.width = b.m["pt"](1.5)
            candidates = self.apply_fill(shape, el.fill, el.fill_to, el.gradient_angle, el.opacity, el.shadow)
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
        shown = (
            [plain_text(line) for line in lines] if el.rich else lines
        )  # what the reader sees, for measuring
        if el.vertical:
            frame._txBody.bodyPr.set("vert", "vert270" if el.vertical == "up" else "vert")
        size = el.size
        gap = 0.3 if el.bullets else 0.1  # space between paragraphs, as a share of the text size
        if el.autofit:
            texts = [(line, 1.0, el.bold) for line in shown]
            box_w, box_h = (el.h, el.w) if el.vertical else (el.w, el.h)  # turned text wraps along the height
            inner_w = box_w - 2 * pad - (0.3 if el.bullets else 0)
            size, fits = fit.fit_size(
                texts,
                inner_w,
                (box_h - 2 * pad) / (el.line_spacing or 1.0),
                el.size,
                el.min_size,
                gap_pt=el.size * gap,
            )
            if not fits:
                b.warn(
                    f"{label}: the text does not fit its box even at {el.min_size:g} pt: enlarge the box or cut words"
                )
        if size < 12:
            b.warn(f"{label}: {size:g} pt text is too small to read in a presentation")
        colour = resolve(theme, el.color)

        def colour_for(token: str) -> str:
            try:
                return resolve(theme, token)
            except (AttributeError, ValueError, IndexError):
                b.warn(f"{label}: '{token}' is not a theme colour or #RRGGBB; the text keeps its own colour")
                return colour

        for number, line in enumerate(lines):
            b.paragraph(
                frame,
                number == 0,
                shown[number],
                size,
                colour,
                bold=el.bold,
                italic=el.italic,
                heading=el.font == "title",
                font="Courier New" if el.font == "mono" else None,
                align=el.align,
                bullet=el.bullets,
                after=size * gap,
                runs=parse_runs(line) if el.rich else None,
                colour_for=colour_for,
                line_spacing=el.line_spacing,
                letter_spacing=el.letter_spacing,
            )
        self.placed.append(
            Placed(
                index,
                label,
                el.x,
                el.y,
                el.w,
                el.h,
                fill=self.worst_behind(colour, candidates),
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
        candidates = self.apply_fill(shape, el.fill, el.fill_to, el.gradient_angle, el.opacity, el.shadow)
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
                    font="Courier New" if el.font == "mono" else None,
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
                fill=self.worst_behind(colour, candidates),
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
        if el.frame != "rect":
            effects.set_picture_frame(shape, el.frame)
            if el.frame == "circle" and abs(w - h) > 0.05:
                b.warn(
                    f"{self.name(index, el)}: a circle frame needs a square box (this one is {w:.1f} x {h:.1f} in)"
                )
        if el.shadow != "none":
            effects.set_shadow(shape, el.shadow)
        if el.fit == "cover":  # fill the box and crop what spills over, evenly
            if ratio > box_ratio:
                shape.crop_left = shape.crop_right = (1 - box_ratio / ratio) / 2
            else:
                shape.crop_top = shape.crop_bottom = (1 - ratio / box_ratio) / 2
        label = self.name(index, el)
        if not el.alt:
            b.warn(f"{label}: the picture has no alt text: say what it shows")
        self.placed.append(Placed(index, label, x, y, w, h))

    def icon(self, slide: Any, index: int, el: IconElement) -> None:
        """An icon as one freeform shape (all its contours), optionally on a badge; recolourable like any shape."""
        b, theme = self.b, self.theme
        label = self.name(index, el)
        try:
            icon = load_icon(el.name)
        except IconError as error:
            b.warn(f"{label}: {error}")
            return
        side = min(el.w, el.h)
        if abs(el.w - el.h) > 0.05:
            b.warn(
                f"{label}: an icon needs a square box (this one is {el.w:.1f} x {el.h:.1f} in); using the smaller side"
            )
        cx, cy = el.x + el.w / 2, el.y + el.h / 2
        if el.badge:
            kind = b.m["shape"].OVAL if el.badge_shape == "circle" else b.m["shape"].ROUNDED_RECTANGLE
            badge = slide.shapes.add_shape(
                kind, *(b.m["inches"](v) for v in (cx - side / 2, cy - side / 2, side, side))
            )
            badge.fill.solid()
            badge.fill.fore_color.rgb = b.colour(resolve(theme, el.badge))
            badge.line.fill.background()
            badge.shadow.inherit = False
            if el.badge_shape == "rounded":
                badge.adjustments[0] = 0.22
            badge._element.nvSpPr.cNvPr.set("descr", "")  # decorative
            drawn = side * 0.56
        else:
            drawn = side
        unit = 1000  # local units per icon side; the freeform builder wants whole numbers
        emu_per_unit = b.m["inches"](drawn) / unit
        left, top = cx - drawn / 2, cy - drawn / 2
        builder = None
        for contour in icon.contours:
            points = [(round(x * unit), round(y * unit)) for x, y in contour.points]
            if builder is None:
                builder = slide.shapes.build_freeform(points[0][0], points[0][1], scale=emu_per_unit)
            else:
                builder.move_to(points[0][0], points[0][1])
            builder.add_line_segments(points[1:], close=contour.closed)
        if builder is None:
            return
        shape = builder.convert_to_shape(b.m["inches"](left), b.m["inches"](top))
        colour = b.colour(resolve(theme, el.color))
        shape.shadow.inherit = False
        if icon.stroke:
            shape.fill.background()
            shape.line.color.rgb = colour
            shape.line.width = b.m["pt"](max(1.0, drawn * 72 * icon.stroke_fraction * el.weight))
            outline = shape.line._get_or_add_ln()
            outline.set("cap", "rnd")
            outline.append(outline.makeelement(b.m["qn"]("a:round"), {}))
        else:
            shape.fill.solid()
            shape.fill.fore_color.rgb = colour
            shape.line.fill.background()
        shape._element.nvSpPr.cNvPr.set(
            "descr", el.alt or f"{icon.name.split(':')[1].replace('-', ' ').replace('_', ' ')} icon"
        )
        shape.name = f"Icon {icon.name}"
        self.placed.append(Placed(index, label, cx - side / 2, cy - side / 2, side, side))

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
        if (
            self.spec.background_image
            and self.spec.scrim < 0.3
            and any(p.has_text and p.fill is None for p in self.placed)
        ):
            warn(
                "text sits over a background picture without a scrim: raise `scrim` (0.4 to 0.7) so it stays readable"
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
                self.worst_behind(item.text_colour, self.backgrounds) or self.background,
            )
            ratio = contrast(item.text_colour, behind)
            large = item.text_size >= 24 or (item.bold and item.text_size >= 18.66)
            if ratio < (3.0 if large else 4.5):
                warn(f"{item.label}: low contrast ({ratio:.1f}:1) between the text and what is behind it")


def build_freeform(builder: Any, spec: FreeformSlide) -> None:
    form = _Freeform(builder, spec)
    slide = builder.new_slide("freeform", spec.title, spec.notes, form.background)
    form.layer_background(slide)
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
        elif isinstance(element, IconElement):
            form.icon(slide, index, element)
        elif isinstance(element, ChartElement):
            form.chart(slide, index, element)
        else:
            form.table(slide, index, element)
    if spec.footer:
        builder.add_footer(slide)
    form.check()
