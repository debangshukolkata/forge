"""Finding slides and shapes for the edit operations (D-289). A shape is named by its id, its exact name, or by what it says
(`"text:Revenue"` = the shape whose text contains it)."""

from __future__ import annotations

from typing import Any

from forge.slides.open_deck import DeckError

TEXT_PREFIX = "text:"


def slide_at(deck: Any, number: int) -> Any:
    if not 1 <= number <= len(deck.slides):
        raise DeckError(f"there is no slide {number} (the deck has {len(deck.slides)})")
    return deck.slides[number - 1]


def walk(shapes: Any) -> Any:
    for shape in shapes:
        yield shape
        if shape.shape_type == 6:  # a group
            yield from walk(shape.shapes)


def shape_text(shape: Any) -> str:
    if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
        return str(shape.text_frame.text)
    if getattr(shape, "has_table", False) and shape.has_table:
        return " ".join(cell.text for row in shape.table.rows for cell in row.cells)
    return ""


def find_shape(slide: Any, ref: int | str) -> Any:
    if isinstance(ref, str) and ref.startswith(TEXT_PREFIX):
        needle = ref[len(TEXT_PREFIX) :].strip().lower()
        matches = [s for s in walk(slide.shapes) if needle and needle in shape_text(s).lower()]
    else:
        wanted_id = int(ref) if isinstance(ref, int) or str(ref).isdigit() else None
        matches = [
            s
            for s in walk(slide.shapes)
            if (wanted_id is not None and s.shape_id == wanted_id) or s.name == ref
        ]
    if not matches:
        shown = ", ".join(f'{s.shape_id} "{s.name}"' for s in walk(slide.shapes))
        raise DeckError(f"no shape {ref!r} on that slide (shapes: {shown})")
    if len(matches) > 1:
        raise DeckError(
            f"{len(matches)} shapes match {ref!r}: use the id ("
            + ", ".join(str(s.shape_id) for s in matches)
            + ")"
        )
    return matches[0]
