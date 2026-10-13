"""Reading a deck out to other forms (TODO P2.16, D-317): the text as Markdown (slides as headings, bullets, tables, chart data, links,
alt text, notes, hidden slides, comments, sections, animations in a line) and the embedded pictures as files. Reading only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge.slides.edit_find import walk
from forge.slides.features import (
    animations_of,
    is_hidden,
    read_comments,
    read_sections,
    transition_of,
)

SKIPPED_PLACEHOLDERS = {"FOOTER", "SLIDE_NUMBER", "DATE"}
MAX_CHART_ROWS = 40
IMAGE_SUFFIX = {
    "jpeg": ".jpg",
    "jpg": ".jpg",
    "png": ".png",
    "gif": ".gif",
    "bmp": ".bmp",
    "tiff": ".tif",
    "x-emf": ".emf",
    "x-wmf": ".wmf",
}


def _escape_cell(text: str) -> str:
    return text.replace("|", r"\|").replace("\n", " ").strip()


def _runs_markdown(paragraph: Any) -> str:
    parts = []
    for run in paragraph.runs:
        text = run.text
        link = getattr(run.hyperlink, "address", None) if hasattr(run, "hyperlink") else None
        if link and text.strip():
            text = f"[{text}]({link})"
        elif text.strip() and run.font.bold:
            text = f"**{text.strip()}**" + (" " if text.endswith(" ") else "")
        parts.append(text)
    return "".join(parts).strip()


def _table_markdown(table: Any) -> list[str]:
    rows = [[_escape_cell(cell.text) for cell in row.cells] for row in table.rows]
    if not rows:
        return []
    lines = ["| " + " | ".join(rows[0]) + " |", "|" + " --- |" * len(rows[0])]
    lines += ["| " + " | ".join(row) + " |" for row in rows[1:]]
    return lines


def _number(value: Any) -> str:
    return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)


def _chart_markdown(chart: Any) -> list[str]:
    try:
        plot = chart.plots[0]
        categories = [str(c) for c in plot.categories]
        series = list(plot.series)
    except (AttributeError, IndexError, ValueError):
        return ["(a chart whose data could not be read)"]
    header = ["", *[s.name for s in series]]
    lines = [
        f"Chart ({chart.chart_type.name.lower().replace('_', ' ')}):",
        "",
        "| " + " | ".join(header) + " |",
        "|" + " --- |" * len(header),
    ]
    for index, category in enumerate(categories[:MAX_CHART_ROWS]):
        values = [_number(list(s.values)[index]) if index < len(list(s.values)) else "" for s in series]
        lines.append("| " + " | ".join([_escape_cell(category), *values]) + " |")
    if len(categories) > MAX_CHART_ROWS:
        lines.append(f"(... {len(categories) - MAX_CHART_ROWS} more rows)")
    return lines


def _image_name(slide_number: int, shape: Any) -> str:
    try:
        suffix = IMAGE_SUFFIX.get(shape.image.ext.lower(), "." + shape.image.ext.lower())
    except (AttributeError, ValueError, KeyError):
        suffix = ".bin"
    safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in shape.name)[:40].strip("-") or "picture"
    return f"slide-{slide_number}-{safe}-{shape.shape_id}{suffix}"


def _shape_markdown(shape: Any, slide_number: int, title_element: Any, pictures_folder: str) -> list[str]:
    if (
        shape.is_placeholder
        and shape.placeholder_format.type is not None
        and shape.placeholder_format.type.name in SKIPPED_PLACEHOLDERS
    ):
        return []
    if title_element is not None and shape._element is title_element:
        return []
    if getattr(shape, "has_table", False) and shape.has_table:
        return [*_table_markdown(shape.table), ""]
    if getattr(shape, "has_chart", False) and shape.has_chart:
        return [*_chart_markdown(shape.chart), ""]
    if shape.shape_type == 13:
        alt = (shape._element.xpath("(.//p:cNvPr)[1]/@descr") or [""])[0].strip()
        label = alt or "picture without alt text"
        return [f"![{label}]({pictures_folder}/{_image_name(slide_number, shape)})", ""]
    if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
        paragraphs = [(p.level, _runs_markdown(p)) for p in shape.text_frame.paragraphs]
        paragraphs = [(level, text) for level, text in paragraphs if text]
        if len(paragraphs) > 1:
            return ["  " * level + "- " + text for level, text in paragraphs] + [""]
        return [text for _, text in paragraphs] + ([""] if paragraphs else [])
    return []


def deck_markdown(deck: Any, pictures_folder: str = "pictures") -> str:
    sections = {section.first_slide: section.name for section in read_sections(deck)}
    comments = read_comments(deck)
    out: list[str] = []
    if (deck.core_properties.title or "").strip():
        out += [f"<!-- document title: {deck.core_properties.title.strip()} -->", ""]
    for number, slide in enumerate(deck.slides, start=1):
        title_shape = slide.shapes.title
        title = title_shape.text_frame.text.strip() if title_shape is not None else ""
        if number in sections:
            out += [f"# Section: {sections[number]}", ""]
        out += [f"## Slide {number}: {title or '(no title)'}"]
        flags = []
        if is_hidden(slide):
            flags.append("hidden slide")
        if transition_of(slide):
            flags.append(f"transition {transition_of(slide)}")
        effects = animations_of(slide)
        if effects:
            flags.append(
                f"{len(effects)} animation(s): "
                + ", ".join(f"{effect} {name!r}" for name, effect, _ in effects)
            )
        if flags:
            out.append("_" + "; ".join(flags) + "_")
        out.append("")
        title_element = title_shape._element if title_shape is not None else None
        for shape in walk(slide.shapes):
            if shape.shape_type == 6:  # a group: its children are visited by walk()
                continue
            out += _shape_markdown(shape, number, title_element, pictures_folder)
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            out += [
                f"> Notes: {line}" if i == 0 else f"> {line}"
                for i, line in enumerate(slide.notes_slide.notes_text_frame.text.strip().splitlines())
            ]
            out.append("")
        for comment in comments:
            if comment.slide == number:
                out += [f"> Comment by {comment.author}: {comment.text}", ""]
    return "\n".join(out).rstrip() + "\n"


def extract_pictures(deck: Any, folder: Path) -> list[Path]:
    """Writes every picture of the deck into `folder` (named slide-N-name-id.ext). Returns the files."""
    folder.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for number, slide in enumerate(deck.slides, start=1):
        for shape in walk(slide.shapes):
            if shape.shape_type != 13:
                continue
            target = folder / _image_name(number, shape)
            target.write_bytes(shape.image.blob)
            written.append(target)
    return written
