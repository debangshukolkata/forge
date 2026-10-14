"""The outline a Word document is built from (JSON or YAML, D-342)."""

from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import BaseModel, Field, ValidationError

from forge.brand.kit import BrandKit
from forge.errors import ForgeError


class DocumentError(ForgeError):
    """The outline or the document is wrong; the message says what to change."""


class Run(BaseModel):
    text: str
    bold: bool = False
    italic: bool = False
    link: str | None = Field(default=None, description="A web address (https://...) this text links to")
    footnote: str | None = Field(default=None, description="A footnote whose mark follows this text")


class Heading(BaseModel):
    type: Literal["heading"] = "heading"
    level: int = Field(default=1, ge=1, le=4)
    text: str


class Paragraph(BaseModel):
    type: Literal["paragraph"] = "paragraph"
    text: str = ""
    runs: list[Run] = Field(default_factory=list, description="Use instead of text for bold, italic or links")


class Bullets(BaseModel):
    type: Literal["bullets"] = "bullets"
    items: list[str]


class Numbered(BaseModel):
    type: Literal["numbered"] = "numbered"
    items: list[str]


class Table(BaseModel):
    type: Literal["table"] = "table"
    header: list[str]
    rows: list[list[str]]
    caption: str = ""
    widths_in: list[float] = Field(default_factory=list)


class Image(BaseModel):
    type: Literal["image"] = "image"
    path: str
    alt: str = Field(description="What the picture shows, for readers who cannot see it (required)")
    width_in: float = 5.5
    caption: str = ""


class Quote(BaseModel):
    type: Literal["quote"] = "quote"
    text: str


class PageBreak(BaseModel):
    type: Literal["page_break"] = "page_break"


Block = Annotated[
    Heading | Paragraph | Bullets | Numbered | Table | Image | Quote | PageBreak, Field(discriminator="type")
]


class DocumentSpec(BaseModel):
    title: str
    author: str = ""
    language: str = "en-GB"
    header: str = ""
    footer: str = ""
    page_numbers: bool = True
    toc: bool = Field(
        default=False, description="A table of contents after the title (Word fills it on opening)"
    )
    font: str = "Calibri"
    font_size: float = 11
    template: str | None = Field(
        default=None, description="A .docx or .dotx whose styles, header and footer are used"
    )
    brand: BrandKit | None = Field(
        default=None, description="Company colours and fonts: headings, table headers and body font follow it"
    )
    blocks: list[Block]


def parse_document(text: str, as_yaml: bool = False) -> DocumentSpec:
    try:
        if as_yaml:
            import yaml

            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
        return DocumentSpec.model_validate(data)
    except (ValueError, ValidationError) as error:
        raise DocumentError(f"The document outline is not valid: {str(error)[:600]}") from error
    except Exception as error:  # yaml errors
        raise DocumentError(f"The document outline could not be read: {str(error)[:300]}") from error
