"""More edit operations (D-289, TODO P2.12): replace a picture keeping its crop and place, format text run by run, change the theme's
fonts and colours, add and remove table rows and columns, change a chart's type or look, footers and slide numbers, notes for many
slides at once, delete a shape, remove empty placeholders. `edit.py` holds the models in its operation list and calls `apply_more`."""

from __future__ import annotations

import re
from collections.abc import Callable
from copy import deepcopy
from typing import Any, Literal

from pydantic import Field

from forge.slides.edit_base import HEX
from forge.slides.edit_base import Op as _Op
from forge.slides.edit_base import rgb as _rgb
from forge.slides.edit_features import FEATURE_OPERATIONS, FEATURE_TYPES, FeatureOperation, apply_feature
from forge.slides.edit_find import find_shape, slide_at, walk
from forge.slides.edit_objects import (
    ChartFormat,
    ChartType,
    TableColumns,
    TableRows,
    _change_chart_type,
    _format_chart,
    _table_columns,
    _table_rows,
)
from forge.slides.open_deck import DeckError

NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
FOOTER_TYPES = {"ftr": "FOOTER", "sldNum": "SLIDE_NUMBER"}
THEME_COLOURS = (
    "dk1",
    "lt1",
    "dk2",
    "lt2",
    "accent1",
    "accent2",
    "accent3",
    "accent4",
    "accent5",
    "accent6",
    "hlink",
    "folHlink",
)


class ReplacePicture(_Op):
    op: Literal["replace_picture"]
    slide: int
    shape: int | str
    image: str  # a picture file in the project; its crop, position and size are kept


class FormatText(_Op):
    op: Literal["format_text"]
    slide: int | None = None  # default every slide
    shape: int | str | None = None  # default every text shape
    find: str | None = None  # only this text inside the shape; default all of it
    bold: bool | None = None
    italic: bool | None = None
    underline: bool | None = None
    size: float | None = Field(default=None, gt=4, le=200)  # points
    color: str | None = Field(default=None, pattern=HEX)
    font: str | None = None


class SetTheme(_Op):
    op: Literal["set_theme"]
    heading_font: str | None = None
    body_font: str | None = None
    colors: dict[str, str] = Field(
        default_factory=dict
    )  # dk1, lt1, dk2, lt2, accent1..accent6, hlink, folHlink


class SetFooter(_Op):
    op: Literal["set_footer"]
    text: str | None = None  # footer text on every slide (or the listed ones)
    slide_numbers: bool | None = None
    slides: list[int] | None = None


class SetNotesBulk(_Op):
    op: Literal["set_notes_bulk"]
    notes: dict[int, str]  # slide number -> notes


class DeleteShape(_Op):
    op: Literal["delete_shape"]
    slide: int
    shape: int | str  # a group is deleted with everything in it


class RemoveEmptyPlaceholders(_Op):
    op: Literal["remove_empty_placeholders"]
    slide: int | None = None  # default every slide


MoreOperation = (
    ReplacePicture
    | FormatText
    | SetTheme
    | TableRows
    | TableColumns
    | ChartType
    | ChartFormat
    | SetFooter
    | SetNotesBulk
    | DeleteShape
    | RemoveEmptyPlaceholders
    | FeatureOperation
)
MORE_OPERATIONS = (
    "replace_picture, format_text, set_theme, add_table_row, delete_table_row, add_table_column, delete_table_column, "
    "change_chart_type, format_chart, set_footer, set_notes_bulk, delete_shape, remove_empty_placeholders, "
    + FEATURE_OPERATIONS
)
MORE_TYPES = (
    ReplacePicture,
    FormatText,
    SetTheme,
    TableRows,
    TableColumns,
    ChartType,
    ChartFormat,
    SetFooter,
    SetNotesBulk,
    DeleteShape,
    RemoveEmptyPlaceholders,
)


# --- pictures ---


def _replace_picture(deck: Any, op: ReplacePicture, read_image: Callable[[str], bytes] | None) -> str:
    import io

    shape = find_shape(slide_at(deck, op.slide), op.shape)
    if shape.shape_type != 13:
        raise DeckError(f'"{shape.name}" is not a picture')
    if read_image is None:
        raise DeckError("pictures cannot be read here")
    try:
        data = read_image(op.image)
    except (OSError, ValueError, KeyError) as error:
        raise DeckError(f"the picture {op.image!r} could not be read: {error}") from error
    _, rel_id = slide_at(deck, op.slide).part.get_or_add_image_part(io.BytesIO(data))
    shape._element.blipFill.blip.rEmbed = rel_id  # the srcRect (crop) and the frame stay as they were
    return f'replaced the picture "{shape.name}" on slide {op.slide}'


# --- text formatting ---


def _split_run(run_element: Any, find: str) -> list[Any]:
    """Cut one run so each occurrence of `find` is a run of its own; returns those runs."""
    text = run_element.t.text or ""
    pieces = re.split(f"({re.escape(find)})", text)
    created: list[Any] = []
    anchor = run_element
    for index, piece in enumerate(pieces):
        if piece == "":
            continue
        target = run_element if anchor is run_element and not created else deepcopy(run_element)
        if target is not run_element:
            anchor.addnext(target)
        target.t.text = piece
        anchor = target
        if piece == find and index % 2 == 1:
            created.append(target)
    return created


def _target_runs(paragraph: Any, find: str | None) -> list[Any]:
    from pptx.text.text import _Run

    if find is None:
        return list(paragraph.runs)
    joined = "".join(r.text for r in paragraph.runs)
    if find not in joined:
        return []
    if not any(find in r.text for r in paragraph.runs):  # split across runs: merge them into the first
        first, *rest = paragraph.runs
        first.text = joined
        for run in rest:
            run._r.getparent().remove(run._r)
    elements = []
    for run in list(paragraph.runs):
        if find in run.text:
            elements.extend(_split_run(run._r, find))
    return [_Run(element, paragraph) for element in elements]


def _style_run(run: Any, op: FormatText) -> None:
    from pptx.util import Pt

    if op.bold is not None:
        run.font.bold = op.bold
    if op.italic is not None:
        run.font.italic = op.italic
    if op.underline is not None:
        run.font.underline = op.underline
    if op.size is not None:
        run.font.size = Pt(op.size)
    if op.color is not None:
        run.font.color.rgb = _rgb(op.color)
    if op.font is not None:
        run.font.name = op.font


def _format_text(deck: Any, op: FormatText) -> str:
    if all(v is None for v in (op.bold, op.italic, op.underline, op.size, op.color, op.font)):
        raise DeckError("give at least one of bold, italic, underline, size, color, font")
    slides = [slide_at(deck, op.slide)] if op.slide else list(deck.slides)
    count = 0
    for slide in slides:
        shapes = [find_shape(slide, op.shape)] if op.shape is not None else list(walk(slide.shapes))
        for shape in shapes:
            frames = []
            if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
                frames.append(shape.text_frame)
            if getattr(shape, "has_table", False) and shape.has_table:
                frames += [cell.text_frame for row in shape.table.rows for cell in row.cells]
            for frame in frames:
                for paragraph in frame.paragraphs:
                    for run in _target_runs(paragraph, op.find):
                        _style_run(run, op)
                        count += 1
    if not count:
        raise DeckError("no text matched" + (f" {op.find!r}" if op.find else ""))
    return f"formatted {count} piece(s) of text"


# --- theme ---


def _theme_part(deck: Any) -> Any:
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT

    return deck.slide_master.part.part_related_by(RT.THEME)


def _set_theme(deck: Any, op: SetTheme) -> str:
    if not (op.heading_font or op.body_font or op.colors):
        raise DeckError("give heading_font, body_font or colors")
    part = _theme_part(deck)
    xml = part.blob.decode("utf-8")
    done = []
    for key, value in op.colors.items():
        if key not in THEME_COLOURS or not re.fullmatch(HEX, value):
            raise DeckError(
                f"colour {key}={value!r}: names are {', '.join(THEME_COLOURS)}; values are hex like 0B6E4F"
            )
        xml, hits = re.subn(
            rf"(<a:{key}>)\s*<a:(?:srgbClr|sysClr)\b[^>]*?(?:/>|>.*?</a:(?:srgbClr|sysClr)>)",
            rf'\1<a:srgbClr val="{value.lstrip("#").upper()}"/>',
            xml,
            count=1,
            flags=re.S,
        )
        if not hits:
            raise DeckError(f"the theme has no colour {key}")
        done.append(key)
    for tag, name in (("majorFont", op.heading_font), ("minorFont", op.body_font)):
        if name:
            xml, hits = re.subn(rf'(<a:{tag}>\s*<a:latin typeface=")[^"]*"', rf'\1{name}"', xml, count=1)
            if not hits:
                raise DeckError("the theme has no font scheme to change")
            done.append("heading font" if tag == "majorFont" else "body font")
    part._blob = xml.encode("utf-8")
    return "changed the theme: " + ", ".join(done)


# --- footers, notes, shapes ---


def _footer_shape(slide: Any, layout_holder: Any, text: str | None, number: bool) -> None:
    from pptx.oxml import parse_xml

    kind = layout_holder._element.xpath(".//p:ph/@type")[0]
    index = layout_holder.placeholder_format.idx
    existing = [p for p in slide.placeholders if p.placeholder_format.idx == index]
    if existing:
        if text is not None and kind == "ftr":
            existing[0].text_frame.text = text
        return
    shape_id = max([s.shape_id for s in slide.shapes] + [1]) + 1
    body = (
        '<a:fld id="{B6F15528-21DE-4FAA-801E-634DDDAF4B2B}" type="slidenum"><a:t>&#8249;#&#8250;</a:t></a:fld>'
        if kind == "sldNum"
        else f"<a:r><a:t>{(text or '').replace('&', '&amp;').replace('<', '&lt;')}</a:t></a:r>"
    )
    element = parse_xml(
        f'<p:sp xmlns:p="{NS_P}" xmlns:a="{NS_A}"><p:nvSpPr><p:cNvPr id="{shape_id}" name="{layout_holder.name}"/>'
        f'<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr><p:nvPr><p:ph type="{kind}" sz="quarter" idx="{index}"/></p:nvPr></p:nvSpPr>'
        f"<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/><a:p>{body}</a:p></p:txBody></p:sp>"
    )
    slide.shapes._spTree.append(element)


def _set_footer(deck: Any, op: SetFooter) -> str:
    if op.text is None and op.slide_numbers is None:
        raise DeckError("give text and/or slide_numbers")
    numbers = op.slides or range(1, len(deck.slides) + 1)
    missing = 0
    for number in numbers:
        slide = slide_at(deck, number)
        for holder in slide.slide_layout.placeholders:
            kind = holder._element.xpath(".//p:ph/@type")
            kind = kind[0] if kind else ""
            if kind == "ftr" and op.text is not None:
                _footer_shape(slide, holder, op.text, False)
            elif kind == "sldNum" and op.slide_numbers:
                _footer_shape(slide, holder, None, True)
        if op.slide_numbers is False:
            for placeholder in list(slide.placeholders):
                if (
                    placeholder.placeholder_format.type is not None
                    and placeholder.placeholder_format.type.name == "SLIDE_NUMBER"
                ):
                    placeholder._element.getparent().remove(placeholder._element)
        if op.text and not any(
            h._element.xpath(".//p:ph[@type='ftr']") for h in slide.slide_layout.placeholders
        ):
            missing += 1
    note = f" ({missing} slide(s) use a layout without a footer area)" if missing else ""
    return "set the footer / slide numbers" + note


def _set_notes_bulk(deck: Any, op: SetNotesBulk) -> str:
    for number, text in op.notes.items():
        slide_at(deck, number).notes_slide.notes_text_frame.text = text
    return f"set the notes of {len(op.notes)} slide(s)"


def _delete_shape(deck: Any, op: DeleteShape) -> str:
    shape = find_shape(slide_at(deck, op.slide), op.shape)
    name = shape.name
    shape._element.getparent().remove(shape._element)
    return f'deleted "{name}" from slide {op.slide}'


def _remove_empty(deck: Any, op: RemoveEmptyPlaceholders) -> str:
    slides = [slide_at(deck, op.slide)] if op.slide else list(deck.slides)
    count = 0
    for slide in slides:
        for holder in list(slide.placeholders):
            kind = holder.placeholder_format.type
            if kind is not None and kind.name in ("DATE", "FOOTER", "SLIDE_NUMBER"):
                continue
            if (
                getattr(holder, "has_text_frame", False)
                and holder.has_text_frame
                and not holder.text_frame.text.strip()
            ):
                holder._element.getparent().remove(holder._element)
                count += 1
    return f"removed {count} empty placeholder(s)"


def apply_more(
    deck: Any,
    operation: Any,
    read_image: Callable[[str], bytes] | None,
    open_source: Callable[[str], Any] | None = None,
) -> str:
    if isinstance(operation, FEATURE_TYPES):
        return apply_feature(deck, operation, open_source)
    if isinstance(operation, ReplacePicture):
        return _replace_picture(deck, operation, read_image)
    if isinstance(operation, FormatText):
        return _format_text(deck, operation)
    if isinstance(operation, SetTheme):
        return _set_theme(deck, operation)
    if isinstance(operation, TableRows):
        return _table_rows(deck, operation)
    if isinstance(operation, TableColumns):
        return _table_columns(deck, operation)
    if isinstance(operation, ChartType):
        return _change_chart_type(deck, operation)
    if isinstance(operation, ChartFormat):
        return _format_chart(deck, operation)
    if isinstance(operation, SetFooter):
        return _set_footer(deck, operation)
    if isinstance(operation, SetNotesBulk):
        return _set_notes_bulk(deck, operation)
    if isinstance(operation, DeleteShape):
        return _delete_shape(deck, operation)
    return _remove_empty(deck, operation)
