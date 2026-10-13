"""Two more everyday layouts (D-294): `cards` (2 to 4 parallel points, each with a heading and a short text) and `steps` (2 to 5 numbered
steps in a row). Models fall back on plain bullet lists because a row of cards used to take a hand-placed freeform slide; these make the
better layout as easy to ask for as bullets. Drawn in the theme's colours; a template deck draws them in its free area."""

from __future__ import annotations

from typing import Any

from forge.slides import fit
from forge.slides.errors import BuildError
from forge.slides.spec import CardsSlide, StepsSlide

GAP = 0.4
MAX_CARD_HEIGHT = 4.6
MIN_TEXT_PT = 16
SAFE_WIDTH = (
    0.88  # PowerPoint wraps earlier and spaces lines wider than the estimate: fit into less than the box
)
SAFE_HEIGHT = 0.85


def _circle(builder: Any, slide: Any, x: float, y: float, diameter: float, fill: str) -> Any:
    shape = slide.shapes.add_shape(
        builder.m["shape"].OVAL, *(builder.m["inches"](v) for v in (x, y, diameter, diameter))
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = builder.colour(fill)
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def _badge(builder: Any, slide: Any, x: float, y: float, text: str, diameter: float = 0.6) -> None:
    _circle(builder, slide, x, y, diameter, builder.theme.accent)
    frame = builder.textbox(slide, x, y, diameter, diameter, "middle")
    builder.paragraph(
        frame, True, text, 20, builder.theme.accent_text, bold=True, heading=True, align="center"
    )


def _heading_and_text(
    builder: Any,
    slide: Any,
    x: float,
    y: float,
    width: float,
    height: float,
    heading: str,
    text: str,
    heading_size: float,
    align: str = "left",
) -> None:
    """A bold heading above a short text, sized to fit the box; says so when the words do not fit."""
    theme = builder.theme
    h_size, h_fits = fit.fit_size(
        [(heading, 1.0, True)], width * SAFE_WIDTH, 0.9 * SAFE_HEIGHT, heading_size, 18
    )
    frame = builder.textbox(slide, x, y, width, 1.0, "top")
    builder.paragraph(frame, True, heading, h_size, theme.text, bold=True, heading=True, align=align)
    if not h_fits:
        builder.warn(f"the heading '{heading[:30]}' is too long for its card: shorten it")
    if text:
        t_height = max(height - 1.0, 0.5)
        t_size, t_fits = fit.fit_size(
            [(text, 1.0, False)], width * SAFE_WIDTH, t_height * SAFE_HEIGHT, 22, MIN_TEXT_PT
        )
        body = builder.textbox(slide, x, y + 1.0, width, t_height, "top")
        builder.paragraph(
            body,
            True,
            text,
            t_size,
            theme.muted if theme.muted != theme.background else theme.text,
            align=align,
        )
        if not t_fits:
            builder.warn(
                f"the text of '{heading[:30]}' is too long for its card at {MIN_TEXT_PT} pt: cut words or split the slide"
            )


def cards_slide(builder: Any, spec: CardsSlide) -> None:
    slide = builder.content_slide(spec.layout, spec.title, spec.notes)
    count = len(spec.items)
    if not 2 <= count <= 4:
        raise BuildError(f"slide {builder.report.number}: a cards slide shows 2 to 4 cards, not {count}")
    area = builder.body_bottom - builder.body_top
    height = min(MAX_CARD_HEIGHT, area - 0.2)
    top = builder.body_top + (area - height) / 2  # the row sits in the middle of the free area
    width = (builder.content_width - GAP * (count - 1)) / count
    for index, card in enumerate(spec.items):
        x = builder.margin + index * (width + GAP)
        builder.rectangle(slide, x, top, width, height, builder.theme.surface, rounded=True)
        inner_x, inner_w, y = x + 0.3, width - 0.6, top + 0.3
        label = card.number or (str(index + 1) if spec.numbered else "")
        if label:
            _badge(builder, slide, inner_x, y, label)
            y += 0.85
        _heading_and_text(
            builder, slide, inner_x, y, inner_w, height - (y - top) - 0.2, card.heading, card.text, 24
        )


def steps_slide(builder: Any, spec: StepsSlide) -> None:
    slide = builder.content_slide(spec.layout, spec.title, spec.notes)
    count = len(spec.steps)
    if not 2 <= count <= 5:
        raise BuildError(f"slide {builder.report.number}: a steps slide shows 2 to 5 steps, not {count}")
    width = builder.content_width / count
    diameter = 0.8
    block = min(4.4, builder.body_bottom - builder.body_top - 0.2)  # circle, heading and a short text
    top = builder.body_top + max((builder.body_bottom - builder.body_top - block) / 2, 0.2)
    line_y = top + diameter / 2 - 0.02
    first_centre = builder.margin + width / 2
    last_centre = builder.margin + width * (count - 0.5)
    builder.rectangle(slide, first_centre, line_y, last_centre - first_centre, 0.04, builder.theme.muted)
    for index, step in enumerate(spec.steps):
        centre = builder.margin + width * (index + 0.5)
        _circle(builder, slide, centre - diameter / 2, top, diameter, builder.theme.accent)
        frame = builder.textbox(slide, centre - diameter / 2, top, diameter, diameter, "middle")
        builder.paragraph(
            frame,
            True,
            str(index + 1),
            26,
            builder.theme.accent_text,
            bold=True,
            heading=True,
            align="center",
        )
        _heading_and_text(
            builder, slide, centre - width / 2 + 0.15, top + diameter + 0.35, width - 0.3, block - diameter - 0.35,
            step.heading, step.text, 26, align="center",
        )  # fmt: skip
