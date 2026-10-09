"""Describes an existing deck in plain text (D-241): every slide with its title, each shape (with the id to
refer to it by), tables, chart data, picture alt text, speaker notes, and the layouts the deck offers. Reading
only: nothing in the file is run or changed."""

from __future__ import annotations

from typing import Any

EMU_PER_INCH = 914400
MAX_TEXT = 1500  # characters shown per shape


def _inches(value: int | None) -> str:
    return f"{(value or 0) / EMU_PER_INCH:.1f}"


def paragraph_lines(frame: Any) -> list[str]:
    """The paragraphs of a text frame, indented two spaces per bullet level."""
    return [
        ("  " * paragraph.level) + "".join(run.text for run in paragraph.runs)
        for paragraph in frame.paragraphs
    ]


def _placeholder_kind(placeholder: Any) -> str:
    kind = placeholder.placeholder_format.type
    return kind.name.lower() if kind else "?"


def _kind(shape: Any) -> str:
    if getattr(shape, "has_chart", False) and shape.has_chart:
        return "chart"
    if getattr(shape, "has_table", False) and shape.has_table:
        return "table"
    if shape.shape_type == 13:
        return "picture"
    if shape.shape_type == 6:
        return "group"
    if shape.is_placeholder:
        return "placeholder"
    return "text" if getattr(shape, "has_text_frame", False) and shape.has_text_frame else "shape"


def _shape_lines(shape: Any, indent: str) -> list[str]:
    kind = _kind(shape)
    position = f"({_inches(shape.left)}, {_inches(shape.top)})"
    where = f"at {position} size {_inches(shape.width)} x {_inches(shape.height)} in"
    head = f'{indent}[id {shape.shape_id}] {kind} "{shape.name}" {where}'
    lines = [head]
    if kind == "table":
        for row in shape.table.rows:
            lines.append(
                f"{indent}    | " + " | ".join(cell.text.replace("\n", " / ") for cell in row.cells) + " |"
            )
    elif kind == "chart":
        chart = shape.chart
        lines.append(
            f"{indent}    {chart.chart_type.name.lower().replace('_', ' ')}; "
            f"categories: {', '.join(str(c) for c in chart.plots[0].categories)}"
        )
        for series in chart.plots[0].series:
            lines.append(f"{indent}    series '{series.name}': {', '.join(str(v) for v in series.values)}")
    elif kind == "picture":
        description = shape._element.nvPicPr.cNvPr.get("descr") or "(no alt text)"
        lines.append(f"{indent}    alt text: {description}")
    elif kind == "group":
        for child in shape.shapes:
            lines.extend(_shape_lines(child, indent + "    "))
    elif getattr(shape, "has_text_frame", False) and shape.has_text_frame and shape.text_frame.text.strip():
        text = "\n".join(f"{indent}    {line}" for line in paragraph_lines(shape.text_frame))
        lines.append(text if len(text) <= MAX_TEXT else text[:MAX_TEXT] + " ... (cut)")
    return lines


def describe_deck(deck: Any) -> str:
    out = [
        f"Slide size {_inches(deck.slide_width)} x {_inches(deck.slide_height)} in; "
        f"{len(deck.slides)} slides."
    ]
    for number, slide in enumerate(deck.slides, start=1):
        title = slide.shapes.title.text_frame.text if slide.shapes.title is not None else "(no title)"
        out.append(f'\nSlide {number} - layout "{slide.slide_layout.name}" - title: {title or "(empty)"}')
        for shape in slide.shapes:
            out.extend(_shape_lines(shape, "  "))
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip():
            out.append("  notes: " + slide.notes_slide.notes_text_frame.text.replace("\n", " / "))
    out.append("\nLayouts this deck can add slides from (use the name with add_slide):")
    for layout in deck.slide_layouts:
        holders = ", ".join(f"{p.placeholder_format.idx}:{_placeholder_kind(p)}" for p in layout.placeholders)
        out.append(f'  "{layout.name}" - placeholders {holders or "none"}')
    return "\n".join(out)
