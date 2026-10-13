"""The outline a presentation is built from (D-240). The model writes it as JSON or YAML in the workspace;
the shapes below are what `build_presentation` accepts, and every mistake is reported in words the model
can fix."""

from __future__ import annotations

import json
from typing import Annotated, Any, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)

from forge.errors import ForgeError
from forge.slides.layout import LayoutError, expand_layouts
from forge.slides.themes import THEMES


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


Color = Annotated[
    str,
    StringConstraints(
        pattern=r"^(#[0-9A-Fa-f]{6}|text|muted|accent|accent_text|surface|background|series[1-6])$"
    ),
]  # a theme colour by name, or "#RRGGBB"
Align = Literal["left", "center", "right"]


class Series(_Model):
    name: str
    values: list[float] = Field(default_factory=list)
    points: list[tuple[float, float]] | None = None  # scatter charts: [x, y] pairs instead of values
    kind: Literal["line"] | None = None  # in a column chart: draw this series as a line (combination chart)
    axis: Literal["primary", "secondary"] = (
        "primary"  # a line series may use a second value axis on the right
    )


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


class CellSpec(_Model):
    """A table cell with its own look; a plain value in a row is the same as {"text": value}."""

    text: str | int | float = ""
    bold: bool = False
    italic: bool = False
    color: Color | None = None
    fill: Color | None = None
    align: Align | None = None
    size: float | None = Field(default=None, ge=8, le=60)
    colspan: int = Field(default=1, ge=1, le=12)
    rowspan: int = Field(default=1, ge=1, le=20)


class Heatmap(_Model):
    """Shade numeric cells between two colours by their value (low to high)."""

    columns: list[int | str] = Field(
        default_factory=list
    )  # column positions (from 0) or names; empty: every numeric column
    low: Color = "background"
    high: Color = "accent"


class TableBase(_Model):
    columns: list[str]
    rows: list[list[str | int | float | CellSpec]]
    col_widths: list[float] = Field(
        default_factory=list
    )  # relative widths, one per column; default: by text length
    align: list[Align] = Field(default_factory=list)  # one per column; default: numbers right, text left
    formats: list[str] = Field(
        default_factory=list
    )  # one number format per column: #,##0  0.0  0%  $#,##0.00
    style: Literal["striped", "plain", "lines", "grid"] = "striped"  # fills and borders
    header_fill: Color | None = None
    first_column_bold: bool = False
    heatmap: Heatmap | None = None
    size: float | None = Field(default=None, ge=8, le=60)


class TableSlide(_Slide, TableBase):
    layout: Literal["table"]
    title: str
    caption: str = ""
    split_rows: int | None = Field(
        default=None, ge=2, le=20
    )  # more rows than this continue on following slides


ChartKind = Literal[
    "column",
    "bar",
    "line",
    "pie",
    "donut",
    "area",
    "stacked_column",
    "stacked_bar",
    "stacked_area",
    "scatter",
]


class ChartBase(_Model):
    """What a chart can be told (shared by the chart layout and the freeform chart element); everything has a quiet default."""

    kind: ChartKind = "column"
    categories: list[str] = Field(default_factory=list)
    series: list[Series] = Field(default_factory=list)
    data_file: str | None = (
        None  # a CSV or Excel file in the workspace: first column categories, the other columns series
    )
    title: str = ""  # a chart title (usually the slide title says it, so off by default)
    x_title: str = ""
    y_title: str = ""
    number_format: str = ""  # Excel style: 0%, #,##0, $#,##0.0, 0.0"k"
    data_labels: bool | None = None  # None: on for pie, donut and single-series charts, off otherwise
    legend: Literal["auto", "none", "bottom", "right", "top"] = "auto"
    colors: list[Color] = Field(
        default_factory=list
    )  # one per series, in order; default: the theme's chart colours
    point_colors: list[Color] = Field(
        default_factory=list
    )  # one per category (single-series column/bar, pie, donut)
    gridlines: bool = True
    y2_title: str = ""  # the right-hand axis of a combination chart
    y2_number_format: str = ""
    y_min: float | None = None
    y_max: float | None = None
    smooth: bool = False  # smooth the lines
    gap_width: int | None = Field(default=None, ge=0, le=500)  # space between column groups, percent

    @model_validator(mode="after")
    def _has_data(self) -> ChartBase:
        if not self.series and not self.data_file:
            raise ValueError("a chart needs `series` (with `categories`) or a `data_file`")
        return self


class ChartSlide(_Slide, ChartBase):
    layout: Literal["chart"]
    title: str
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


class Card(_Model):
    heading: str
    text: str = ""
    number: str | None = None  # a badge on the card; default the position when `numbered` is on


class CardsSlide(_Slide):
    """2 to 4 parallel points side by side: a heading and a short text each (use instead of a bullet list of parallel items)."""

    layout: Literal["cards"]
    title: str
    items: list[Card]
    numbered: bool = False


class Step(_Model):
    heading: str
    text: str = ""


class StepsSlide(_Slide):
    """2 to 5 numbered steps in a row joined by a line: a process, a plan, a rollout."""

    layout: Literal["steps"]
    title: str
    steps: list[Step]


class TemplateSlide(_Slide):
    """A copy of one of the company template's own sample slides, with the content put into its slots (D-290)."""

    layout: Literal["template_slide"]
    source: int = Field(ge=1)  # the sample slide's number in the template (analyze_template lists them)
    fill: dict[str, Any]  # title, subtitle, body (lines), items (the repeated groups), picture, slot:<id>


# --- free-form slides (D-242): the model places every element itself, in inches on a 13.333 x 7.5 canvas ---

VAlign = Literal["top", "middle", "bottom"]
FontKind = Literal["title", "body", "mono"]


Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")]


class _Placed(_Model):
    id: Identifier | None = (
        None  # a name other elements can refer to: connectors, groups, align and distribute
    )
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
    fill_to: Color | None = None  # a second colour makes a linear gradient from `fill` to `fill_to`
    gradient_angle: float = 90  # degrees clockwise: 0 left to right, 90 top to bottom
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)  # fill transparency: 1 solid, 0 invisible
    shadow: Literal["none", "soft", "lifted", "hard"] = "none"
    line: Color | None = None
    rounded: bool = False
    bullets: bool = False
    pad: float | None = None  # inner margin in inches; default 0.15 for a filled box, else 0
    autofit: bool = True  # shrink the text to fit the box, down to min_size
    min_size: float = 12
    rich: bool = (
        False  # inline **bold**, *italic*, [link](https://...) and {accent}colour{/} (see richtext.py)
    )
    line_spacing: float | None = Field(default=None, ge=0.8, le=3.0)  # a multiple of the line height
    letter_spacing: float | None = Field(default=None, ge=-5, le=30)  # points added between letters
    vertical: Literal["up", "down"] | None = None  # text turned to read bottom-to-top or top-to-bottom


class ShapeElement(_Placed):
    type: Literal["shape"]
    shape: Literal[
        "rect", "rounded", "oval", "triangle", "diamond", "chevron", "pentagon", "arrow_right", "plus"
    ] = "rect"
    fill: Color | None = "accent"
    fill_to: Color | None = None  # a second colour makes a linear gradient from `fill` to `fill_to`
    gradient_angle: float = 90  # degrees clockwise: 0 left to right, 90 top to bottom
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)  # fill transparency: 1 solid, 0 invisible
    shadow: Literal["none", "soft", "lifted", "hard"] = "none"
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


class Anchor(_Model):
    """A side of a shape a connector is glued to, so it follows the shape when the shape is moved in PowerPoint."""

    id: Identifier
    side: Literal["top", "right", "bottom", "left"] = "right"


class LineElement(_Model):
    type: Literal["line"]
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 0.0
    y2: float = 0.0
    start: Anchor | None = None  # glue the start to a shape drawn earlier (instead of x1, y1)
    end: Anchor | None = None  # glue the end to a shape drawn earlier (instead of x2, y2)
    kind: Literal["straight", "elbow"] = "straight"
    color: Color = "muted"
    width: float = 2.0
    arrow: bool = False  # an arrow head at the end
    dash: bool = False

    @model_validator(mode="after")
    def _has_ends(self) -> LineElement:
        explicit = {"x1", "y1", "x2", "y2"} <= self.model_fields_set
        if not explicit and not (self.start and self.end):
            raise ValueError("a line needs x1, y1, x2, y2, or `start` and `end` anchors")
        return self


class GroupElement(_Model):
    """Groups elements drawn earlier so they move and resize together in PowerPoint."""

    type: Literal["group"]
    ids: list[Identifier] = Field(min_length=2)
    name: str = ""


class ImageElement(_Placed):
    type: Literal["image"]
    path: str  # a picture in the workspace
    alt: str = ""
    fit: Literal["contain", "cover"] = "contain"  # cover fills the box and crops the overflow
    frame: Literal["rect", "rounded", "circle"] = (
        "rect"  # the shape the picture is cut to (circle: use a square box)
    )
    shadow: Literal["none", "soft", "lifted", "hard"] = "none"


class IconElement(_Placed):
    type: Literal["icon"]
    name: str  # "lucide:rocket", "material:rocket_launch" or a bare name (Lucide first); find names with find_icon
    color: Color = "accent"
    badge: Color | None = (
        None  # a filled circle or rounded square behind the icon (icon in a coloured circle)
    )
    badge_shape: Literal["circle", "rounded"] = "circle"
    weight: float = Field(default=1.0, ge=0.5, le=2.5)  # line thickness multiplier for outline (Lucide) icons
    alt: str = ""


class ChartElement(_Placed, ChartBase):
    type: Literal["chart"]
    alt: str = ""


class TableElement(_Placed, TableBase):
    type: Literal["table"]
    alt: str = ""


Element = Annotated[
    TextElement
    | ShapeElement
    | LineElement
    | GroupElement
    | ImageElement
    | IconElement
    | ChartElement
    | TableElement,
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
    background_to: Color | None = None  # a second colour makes the background a gradient
    background_angle: float = 90
    background_image: str | None = None  # a full-bleed picture behind everything (a workspace path)
    scrim: float = Field(
        default=0.0, ge=0.0, le=0.95
    )  # a layer of the background colour over the picture, for legible text
    footer: bool = False  # the small deck title and slide number at the bottom
    elements: list[Element] = Field(min_length=1, max_length=80)  # in drawing order: first is at the back


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
    | CardsSlide
    | StepsSlide
    | TemplateSlide
    | FreeformSlide,
    Field(discriminator="layout"),
]

LAYOUTS = "title, section, bullets, two_column, image, table, chart, quote, stats, closing, cards, steps, freeform, template_slide"


HexColour = Annotated[str, StringConstraints(pattern=r"^#?[0-9A-Fa-f]{6}$")]


class BrandKit(_Model):
    """Colours and fonts of the user's brand. Give what you know; the rest is derived so text stays readable."""

    accent: HexColour | None = None
    background: HexColour | None = None
    text: HexColour | None = None
    muted: HexColour | None = None
    surface: HexColour | None = None
    accent_text: HexColour | None = None
    title_font: str | None = None
    body_font: str | None = None


class Deck(_Model):
    title: str
    subtitle: str = ""
    author: str = ""
    language: str = Field(
        default="en-US", pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?$"
    )  # the language of the text (en-US, de-DE, ...): screen readers and spell-check use it
    theme: str = "clean"  # one of THEMES (see themes.py / the skill); chosen by audience and topic
    brand: BrandKit | None = None  # a brand kit: colours and fonts that override the theme
    minutes: int | None = Field(
        default=None, ge=1, le=480
    )  # how long the talk is: the build warns when the deck is too long for it
    template: str | None = (
        None  # a .potx or .pptx company template in the workspace: the deck is built on its layouts
    )

    @field_validator("theme")
    @classmethod
    def _known_theme(cls, value: str) -> str:
        if value not in THEMES:
            raise ValueError(f"unknown theme '{value}'; themes are: {', '.join(THEMES)}")
        return value

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
        expand_layouts(data)
    except LayoutError as error:
        raise SpecError(f"The outline has a layout problem: {error}") from error
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
