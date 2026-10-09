"""Estimates whether text fits its box (D-240), so a slide shrinks its text or says it is too full before
anyone opens PowerPoint. The estimate is deliberately a little pessimistic: it assumes an average character
is about half an em wide, which holds for Segoe UI, Calibri and Georgia."""

from __future__ import annotations

CHAR_EM = 0.54  # average character width in em (bold text is wider, see below)
BOLD_EXTRA = 1.07
LINE_HEIGHT = 1.2  # line height in em


def lines_needed(text: str, width_in: float, size_pt: float, bold: bool = False) -> int:
    """How many lines `text` takes when word-wrapped into `width_in` inches at `size_pt`."""
    per_char = CHAR_EM * size_pt / 72 * (BOLD_EXTRA if bold else 1)
    capacity = max(1.0, width_in / per_char)  # characters per line
    lines = 0
    for paragraph in text.split("\n"):
        count, used = 1, 0.0
        for word in paragraph.split():
            if used == 0:
                used = len(word)
            elif used + 1 + len(word) <= capacity:
                used += 1 + len(word)
            else:
                count += 1
                used = len(word)
            while used > capacity:  # a very long word wraps by itself
                count += 1
                used -= capacity
        lines += count
    return lines


def block_height(items: list[tuple[str, float, bool]], width_in: float, gap_pt: float = 0) -> float:
    """Inches a list of (text, size_pt, bold) paragraphs needs, with `gap_pt` between paragraphs."""
    total = 0.0
    for text, size, bold in items:
        total += lines_needed(text, width_in, size, bold) * size * LINE_HEIGHT / 72
        total += gap_pt / 72
    return total


def fit_size(
    texts: list[tuple[str, float, bool]],
    width_in: float,
    height_in: float,
    start: float,
    minimum: float,
    gap_pt: float = 0,
) -> tuple[float, bool]:
    """The largest size between `start` and `minimum` at which every paragraph fits. `texts` hold the size as
    a ratio of the base size (1.0 = base), so a sub-bullet can be 0.85. Returns (size, fits)."""
    size = start
    while size >= minimum:
        scaled = [(text, size * ratio, bold) for text, ratio, bold in texts]
        if block_height(scaled, width_in, gap_pt * size / start) <= height_in:
            return size, True
        size -= 1
    return minimum, False
