"""The design of an existing deck, read as a short summary (TODO P2.24, D-336): what to match when the user says "make new slides in this format".

`read_design(prs)` finds, without rendering: the slide size; the theme colours and fonts of each master; how many slides are dark or
light; where the title sits and how big it is on most slides; the left and right margin of the text; the shapes that repeat on most
slides in the same place (logo, bar, footer line, slide number) with their share; the layouts used; the fonts and sizes the text
really uses; the fill colours most used; and a `brand` kit (accent, background, text, fonts) to paste into an outline. `describe_design`
renders it for the model; `Design.as_dict()` is the same data for programs (the image reader of P2.25 produces the same shape)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from forge.slides.backgrounds import background_luminance, is_dark
from forge.slides.edit_find import walk
from forge.slides.geometry import Geometry
from forge.slides.look import read_masters

EMU = 914400
MIN_SLIDES_FOR_REPEATS = 3
REPEAT_SHARE = 0.5  # a shape on at least this share of the slides, at the same place, belongs to the design
GREY_SPREAD = 24  # a colour whose channels differ less than this is grey: not an accent


@dataclass
class Design:
    width: float
    height: float
    slides: int
    masters: int
    colours: dict[str, str] = field(default_factory=dict)
    heading_font: str = ""
    body_font: str = ""
    dark_slides: int = 0
    light_slides: int = 0
    title: dict[str, float] = field(
        default_factory=dict
    )  # left, top, width, size (inches and points), most common
    margins: tuple[float, float] = (0.0, 0.0)
    repeated: list[dict[str, Any]] = field(default_factory=list)
    layouts: list[tuple[str, int]] = field(default_factory=list)
    fonts: list[tuple[str, int]] = field(default_factory=list)
    sizes: list[tuple[float, int]] = field(default_factory=list)
    fills: list[tuple[str, int]] = field(default_factory=list)
    brand: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "size_in": [round(self.width, 2), round(self.height, 2)],
            "slides": self.slides,
            "masters": self.masters,
            "colours": self.colours,
            "fonts": {
                "heading": self.heading_font,
                "body": self.body_font,
                "used": self.fonts,
                "sizes": self.sizes,
            },
            "dark_slides": self.dark_slides,
            "light_slides": self.light_slides,
            "title": self.title,
            "margins_in": list(self.margins),
            "repeated": self.repeated,
            "layouts": self.layouts,
            "fills": self.fills,
            "brand": self.brand,
        }


def _inches(value: int | None) -> float:
    return round((value or 0) / EMU, 2)


def _is_footer(shape: Any) -> bool:
    return bool(
        shape.is_placeholder
        and shape.placeholder_format.type is not None
        and shape.placeholder_format.type.name in ("FOOTER", "SLIDE_NUMBER", "DATE")
    )


def _fill_hex(shape: Any) -> str | None:
    try:
        if shape.fill.type == 1 and shape.fill.fore_color.type is not None:
            return str(shape.fill.fore_color.rgb)
    except (AttributeError, ValueError, TypeError, KeyError):
        pass
    return None


def _is_grey(value: str) -> bool:
    channels = [int(value[i : i + 2], 16) for i in (0, 2, 4)]
    return max(channels) - min(channels) < GREY_SPREAD


def _title_facts(slide: Any, geo: Geometry) -> tuple[tuple[float, float, float], float | None] | None:
    title = slide.shapes.title
    if title is None or not title.has_text_frame or not title.text_frame.text.strip():
        return None
    left, top, width, _ = geo.box(title)
    if None in (left, top, width):
        return None
    size = next((r.font.size.pt for p in title.text_frame.paragraphs for r in p.runs if r.font.size), None)
    return (_inches(left), _inches(top), _inches(width)), size


def _margin(places: Counter[float], slides: int) -> float:
    """The smallest distance from the edge at which text starts on a fair share of the slides (a lone far-out note does not count)."""
    needed = max(2, slides // 5)
    close = sorted(value for value, count in places.items() if count >= needed)
    return close[0] if close else 0.0


def read_design(prs: Any) -> Design:
    geo = Geometry()
    masters = read_masters(prs)
    first = masters[0] if masters else None
    design = Design(
        width=prs.slide_width / EMU,
        height=prs.slide_height / EMU,
        slides=len(prs.slides),
        masters=len(masters),
        colours=dict(first.colours) if first else {},
        heading_font=first.heading_font if first else "",
        body_font=first.body_font if first else "",
    )
    slides = list(prs.slides)
    titles: Counter[tuple[float, float, float]] = Counter()
    title_sizes: Counter[float] = Counter()
    lefts: Counter[float] = Counter()
    rights: Counter[float] = Counter()
    layouts: Counter[str] = Counter()
    fonts: Counter[str] = Counter()
    sizes: Counter[float] = Counter()
    fills: Counter[str] = Counter()
    seen: Counter[tuple[Any, ...]] = Counter()
    samples: dict[tuple[Any, ...], dict[str, Any]] = {}
    for slide in slides:
        layouts[slide.slide_layout.name] += 1
        dark = is_dark(background_luminance(slide))
        design.dark_slides += dark is True
        design.light_slides += dark is False
        facts = _title_facts(slide, geo)
        if facts:
            titles[facts[0]] += 1
            if facts[1]:
                title_sizes[facts[1]] += 1
        keys_here: set[tuple[Any, ...]] = set()
        for shape in walk(slide.shapes):
            box = geo.full(shape)
            if box is None:
                continue
            if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    for run in paragraph.runs:
                        if run.font.name:
                            fonts[run.font.name] += 1
                        if run.font.size and run.text.strip():
                            sizes[round(run.font.size.pt, 1)] += 1
                if shape.text_frame.text.strip() and not _is_footer(shape):
                    lefts[round(box[0] / EMU, 1)] += 1
                    rights[
                        round(
                            (slide.part.package.presentation_part.presentation.slide_width - box[0] - box[2])
                            / EMU,
                            1,
                        )
                    ] += 1
            colour = _fill_hex(shape)
            if colour:
                fills[colour.upper()] += 1
            if (
                shape.is_placeholder
                and shape.placeholder_format.type is not None
                and shape.placeholder_format.type.name in ("TITLE", "CENTER_TITLE")
            ):
                continue
            text = (
                shape.text_frame.text.strip()
                if getattr(shape, "has_text_frame", False) and shape.has_text_frame
                else ""
            )
            key = (
                round(box[0] / EMU, 1),
                round(box[1] / EMU, 1),
                round(box[2] / EMU, 1),
                round(box[3] / EMU, 1),
                str(shape.shape_type),
                text[:30],
            )
            if key not in keys_here:
                keys_here.add(key)
                seen[key] += 1
                samples.setdefault(
                    key,
                    {
                        "name": shape.name,
                        "kind": str(shape.shape_type).split(".")[-1].split(" ")[0],
                        "text": text[:40],
                    },
                )
    if titles:
        (left, top, width), _ = titles.most_common(1)[0]
        design.title = {"left": left, "top": top, "width": width}
        if title_sizes:
            design.title["size_pt"] = title_sizes.most_common(1)[0][0]
    if lefts:
        design.margins = (_margin(lefts, len(slides)), _margin(rights, len(slides)))
    if len(slides) >= MIN_SLIDES_FOR_REPEATS:
        for key, count in seen.most_common():
            if count / len(slides) >= REPEAT_SHARE and key[2] > 0 and key[3] > 0:
                design.repeated.append(
                    {
                        **samples[key],
                        "x": key[0],
                        "y": key[1],
                        "w": key[2],
                        "h": key[3],
                        "share": round(count / len(slides), 2),
                    }
                )
        design.repeated = design.repeated[:8]
    design.layouts = layouts.most_common(6)
    design.fonts = fonts.most_common(5)
    design.sizes = sizes.most_common(6)
    design.fills = fills.most_common(8)
    design.brand = _brand(design)
    return design


def _brand(design: Design) -> dict[str, str]:
    """A brand kit for the outline: the theme accent (else the most used colourful fill), a background on the deck's usual side, the
    text colour that reads on it, and the fonts."""
    kit: dict[str, str] = {}
    accent = design.colours.get("accent1")
    colourful = [c for c, _ in design.fills if not _is_grey(c)]
    if colourful and (not accent or accent in ("", "?")):
        accent = colourful[0]
    if accent and accent != "?":
        kit["accent"] = "#" + accent.lstrip("#").upper()
    dark = design.dark_slides > design.light_slides
    background = design.colours.get("dk1" if dark else "lt1", "")
    text = design.colours.get("lt1" if dark else "dk1", "")
    if dark and background in ("", "000000"):
        background = "0A0A0A"
    if background and background != "?":
        kit["background"] = "#" + background.lstrip("#").upper()
    if text and text != "?":
        kit["text"] = "#" + text.lstrip("#").upper()
    if design.heading_font and not design.heading_font.startswith("+"):
        kit["title_font"] = design.heading_font
    if design.body_font and not design.body_font.startswith("+"):
        kit["body_font"] = design.body_font
    return kit


def _repeated_line(r: dict[str, Any]) -> str:
    said = ' "' + r["text"] + '"' if r["text"] else ""
    return (
        f"{r['name']}{said} at ({r['x']:g}, {r['y']:g}) {r['w']:g} x {r['h']:g} in, {int(r['share'] * 100)}%"
    )


def describe_design(design: Design, name: str = "the deck") -> str:
    side = (
        "mostly dark"
        if design.dark_slides > design.light_slides * 1.5
        else "mostly light"
        if design.light_slides > design.dark_slides * 1.5
        else "dark and light"
    )
    lines = [
        f"Design of {name}: {design.slides} slides of {design.width:.2f} x {design.height:.2f} in, {design.masters} master(s); slides are {side} "
        f"({design.dark_slides} dark, {design.light_slides} light, the rest in between or not readable from the file).",
        "theme colours: " + " ".join(f"{k}={v}" for k, v in design.colours.items() if v and v != "?"),
        f"theme fonts: {design.heading_font or '?'} (headings) / {design.body_font or '?'} (text); fonts the text really uses: "
        + (", ".join(f"{n} x{c}" for n, c in design.fonts) or "none set on the text (it follows the theme)"),
    ]
    if design.title:
        size = f", {design.title['size_pt']:g} pt" if "size_pt" in design.title else ""
        lines.append(
            f"titles: at {design.title['left']:g} in from the left and {design.title['top']:g} in from the top, {design.title['width']:g} in wide{size}"
        )
    if any(design.margins):
        lines.append(f"text margins: {design.margins[0]:g} in left, {design.margins[1]:g} in right")
    if design.sizes:
        lines.append("text sizes in use (pt): " + ", ".join(f"{s:g} x{c}" for s, c in design.sizes))
    if design.repeated:
        lines.append(
            "repeated on most slides (the design's frame; keep them): "
            + "; ".join(_repeated_line(r) for r in design.repeated)
        )
    if design.layouts:
        lines.append("layouts used: " + ", ".join(f"{n} x{c}" for n, c in design.layouts))
    if design.fills:
        lines.append("fill colours most used: " + ", ".join(f"#{c} x{n}" for c, n in design.fills))
    if design.brand:
        import json

        lines.append("brand kit to use in an outline: " + json.dumps(design.brand))
    return "\n".join(lines)
