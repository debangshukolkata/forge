"""The outline a presentation is built from (D-240). The model writes it as JSON or YAML in the workspace;
the shapes below are what `build_presentation` accepts, and every mistake is reported in words the model
can fix."""

from __future__ import annotations

import json
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from forge.errors import ForgeError


class SpecError(ForgeError):
    """The outline cannot be used; the message says what to change."""


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BulletGroup(_Model):
    text: str
    sub: list[str] = Field(default_factory=list)


class Column(_Model):
    heading: str = ""
    bullets: list[str | BulletGroup] = Field(default_factory=list)


class Series(_Model):
    name: str
    values: list[float]


class Stat(_Model):
    value: str
    label: str = ""


class _Slide(_Model):
    notes: str = ""  # speaker notes


class TitleSlide(_Slide):
    layout: Literal["title"]
    title: str
    subtitle: str = ""


class SectionSlide(_Slide):
    layout: Literal["section"]
    title: str
    subtitle: str = ""


class BulletsSlide(_Slide):
    layout: Literal["bullets"]
    title: str
    bullets: list[str | BulletGroup]


class TwoColumnSlide(_Slide):
    layout: Literal["two_column"]
    title: str
    left: Column
    right: Column


class ImageSlide(_Slide):
    layout: Literal["image"]
    title: str
    image: str  # a path inside the workspace
    caption: str = ""
    alt: str = ""  # what the picture shows, for screen readers


class TableSlide(_Slide):
    layout: Literal["table"]
    title: str
    columns: list[str]
    rows: list[list[str | int | float]]
    caption: str = ""


class ChartSlide(_Slide):
    layout: Literal["chart"]
    title: str
    kind: Literal["bar", "column", "line", "pie"] = "column"
    categories: list[str]
    series: list[Series]
    caption: str = ""


class QuoteSlide(_Slide):
    layout: Literal["quote"]
    quote: str
    by: str = ""


class StatsSlide(_Slide):
    layout: Literal["stats"]
    title: str
    items: list[Stat]


class ClosingSlide(_Slide):
    layout: Literal["closing"]
    title: str
    subtitle: str = ""


# --- free-form slides (D-242): the model places every element itself, in inches on a 13.333 x 7.5 canvas ---

Color = Annotated[
    str,
    StringConstraints(
        pattern=r"^(#[0-9A-Fa-f]{6}|text|muted|accent|accent_text|surface|background|series[1-6])$"
    ),
]  # a theme colour by name, or "#RRGGBB"
Align = Literal["left", "center", "right"]
VAlign = Literal["top", "middle", "bottom"]
FontKind = Literal["title", "body", "mono"]


class _Placed(_Model):
    x: float
    y: float
    w: float = Field(gt=0)
    h: float = Field(gt=0)


class TextElement(_Placed):
    type: Literal["text"]
    text: str  # paragraphs separated by a new line
    size: float = 20
    bold: bool = False
    italic: bool = False
    color: Color = "text"
    align: Align = "left"
    valign: VAlign = "top"
    font: FontKind = "body"
    fill: Color | None = None  # a filled box (a card, a callout, a label)
    line: Color | None = None
    rounded: bool = False
    bullets: bool = False
    pad: float | None = None  # inner margin in inches; default 0.15 for a filled box, else 0
    autofit: bool = True  # shrink the text to fit the box, down to min_size
    min_size: float = 12


class ShapeElement(_Placed):
    type: Literal["shape"]
    shape: Literal[
        "rect", "rounded", "oval", "triangle", "diamond", "chevron", "pentagon", "arrow_right", "plus"
    ] = "rect"
    fill: Color | None = "accent"
    line: Color | None = None
    line_width: float = 1.5
    text: str = ""  # a label inside the shape
    size: float = 18
    color: Color = "accent_text"
    bold: bool = False
    align: Align = "center"
    valign: VAlign = "middle"
    font: FontKind = "body"
    rotate: float = 0


class LineElement(_Model):
    type: Literal["line"]
    x1: float
    y1: float
    x2: float
    y2: float
    color: Color = "muted"
    width: float = 2.0
    arrow: bool = False  # an arrow head at (x2, y2)
    dash: bool = False


class ImageElement(_Placed):
    type: Literal["image"]
    path: str  # a picture in the workspace
    alt: str = ""
    fit: Literal["contain", "cover"] = "contain"  # cover fills the box and crops the overflow


class ChartElement(_Placed):
    type: Literal["chart"]
    kind: Literal["bar", "column", "line", "pie"] = "column"
    categories: list[str]
    series: list[Series]
    alt: str = ""


class TableElement(_Placed):
    type: Literal["table"]
    columns: list[str]
    rows: list[list[str | int | float]]
    size: float | None = None
    alt: str = ""


Element = Annotated[
    TextElement | ShapeElement | LineElement | ImageElement | ChartElement | TableElement,
    Field(discriminator="type"),
]


class TitleBox(_Model):
    x: float = 0.8
    y: float = 0.5
    w: float = 11.7
    h: float = 1.15
    size: float = 34
    color: Color = "text"
    align: Align = "left"
    valign: Literal["top", "middle", "bottom"] = "bottom"


class FreeformSlide(_Slide):
    layout: Literal["freeform"]
    title: str  # every slide has a real title (navigation, screen readers); hide it with title_visible=false
    title_box: TitleBox = Field(default_factory=TitleBox)
    title_visible: bool = True
    background: Color | None = None
    footer: bool = False  # the small deck title and slide number at the bottom
    elements: list[Element] = Field(min_length=1, max_length=40)  # in drawing order: first is at the back


Slide = Annotated[
    TitleSlide
    | SectionSlide
    | BulletsSlide
    | TwoColumnSlide
    | ImageSlide
    | TableSlide
    | ChartSlide
    | QuoteSlide
    | StatsSlide
    | ClosingSlide
    | FreeformSlide,
    Field(discriminator="layout"),
]

LAYOUTS = "title, section, bullets, two_column, image, table, chart, quote, stats, closing, freeform"


class Deck(_Model):
    title: str
    subtitle: str = ""
    author: str = ""
    theme: Literal["clean", "dark", "warm"] = "clean"
    footer: str = ""  # small text at the bottom of content slides; defaults to the deck title
    slides: list[Slide] = Field(min_length=1)


def parse_deck(text: str, as_yaml: bool = False) -> Deck:
    """The outline from JSON (or YAML) text. Raises SpecError with every problem listed."""
    try:
        data = yaml.safe_load(text) if as_yaml else json.loads(text)
    except (ValueError, yaml.YAMLError) as error:
        raise SpecError(f"The outline is not valid {'YAML' if as_yaml else 'JSON'}: {error}") from error
    if not isinstance(data, dict):
        raise SpecError("The outline must be an object with 'title' and 'slides'.")
    try:
        return Deck.model_validate(data)
    except ValidationError as error:
        problems = []
        for item in error.errors()[:8]:
            where = ".".join(
                str(part) for part in item["loc"] if not str(part).startswith(("function-", "str"))
            )
            problems.append(f"- {where or 'outline'}: {item['msg']}")
        raise SpecError(
            "The outline has problems:\n" + "\n".join(problems) + f"\nLayouts are: {LAYOUTS}."
        ) from error
