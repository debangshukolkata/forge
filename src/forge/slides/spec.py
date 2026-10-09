"""The outline a presentation is built from (D-240). The model writes it as JSON or YAML in the workspace;
the shapes below are what `build_presentation` accepts, and every mistake is reported in words the model
can fix."""

from __future__ import annotations

import json
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

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
    | ClosingSlide,
    Field(discriminator="layout"),
]

LAYOUTS = "title, section, bullets, two_column, image, table, chart, quote, stats, closing"  # for messages


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
