"""Design lint for a deck outline (TODO P1.5 to P1.7, D-276): the checks that catch the generic, machine-made look and
fonts that do not exist everywhere. Pure functions on the outline, so they are cheap and run on every build."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from forge.slides.spec import (
    BulletsSlide,
    ChartSlide,
    ClosingSlide,
    Deck,
    FreeformSlide,
    ImageSlide,
    QuoteSlide,
    SectionSlide,
    ShapeElement,
    StatsSlide,
    TableSlide,
    TitleSlide,
    TwoColumnSlide,
)

# Fonts present on every Windows and Mac PowerPoint install; anything else may be replaced by another font on the
# reader's computer, which changes line breaks and can push text out of its box.
SAFE_FONTS = frozenset(
    {
        "arial",
        "calibri",
        "cambria",
        "georgia",
        "times new roman",
        "courier new",
        "bookman old style",
        "century schoolbook",
    }
)
MAX_TITLE_WORDS = 12
MIN_TAKEAWAY_WORDS = 4
SAME_LAYOUT_RUN = 3
TEXT_ONLY_SHARE = 0.6
ACCENT_BAR_MAX_HEIGHT = 0.12  # inches
TITLE_ZONE_BOTTOM = 2.0
CONTENT_LAYOUTS_WITHOUT_TAKEAWAY = (TitleSlide, ClosingSlide, SectionSlide, QuoteSlide)
VISUAL_LAYOUTS = (ChartSlide, TableSlide, ImageSlide, StatsSlide, FreeformSlide)


def font_warning(name: str) -> str | None:
    """A message when `name` is not a font every Office install has, else None."""
    if name.strip().lower() in SAFE_FONTS:
        return None
    return (
        f"the font '{name}' is not on every computer, so it may be replaced and the text may no longer fit; "
        "use Arial, Calibri, Cambria, Georgia, Times New Roman, Courier New, Bookman Old Style or Century Schoolbook"
    )


def title_warning(title: str) -> str | None:
    """Titles should state the takeaway ("Search is now 4x faster"), not name a topic ("Search")."""
    words = title.split()
    if len(words) > MAX_TITLE_WORDS:
        return f"the title has {len(words)} words: keep it under {MAX_TITLE_WORDS + 1}"
    has_figure = bool(re.search(r"\d", title))
    if len(words) < MIN_TAKEAWAY_WORDS and not has_figure:
        return (
            f"the title '{title}' reads like a topic: say the point instead "
            "(for example 'Search is now 4x faster' rather than 'Search')"
        )
    return None


def slide_title_warnings(deck: Deck) -> dict[int, str]:
    """Slide number (1-based) to a title warning, for slides whose title carries a message."""
    found: dict[int, str] = {}
    for number, slide in enumerate(deck.slides, start=1):
        if isinstance(slide, CONTENT_LAYOUTS_WITHOUT_TAKEAWAY):
            continue
        title = getattr(slide, "title", "") or ""
        message = title_warning(title) if title else None
        if message:
            found[number] = message
    return found


def _accent_bars(slide: FreeformSlide) -> bool:
    """A thin filled rectangle in the title zone: the decoration under a title that marks a machine-made slide."""
    return any(
        isinstance(element, ShapeElement)
        and element.shape == "rect"
        and element.h <= ACCENT_BAR_MAX_HEIGHT
        and element.w >= 0.3
        and element.y <= TITLE_ZONE_BOTTOM
        for element in slide.elements
    )


def _runs(layouts: Sequence[str]) -> Iterable[tuple[int, str]]:
    start = 0
    for index in range(1, len(layouts) + 1):
        if index == len(layouts) or layouts[index] != layouts[start]:
            if index - start >= SAME_LAYOUT_RUN:
                yield start + 1, layouts[start]
            start = index


def deck_warnings(deck: Deck) -> list[str]:
    """Problems of the deck as a whole (not tied to one slide)."""
    out: list[str] = []
    layouts = [slide.layout for slide in deck.slides]
    for first, layout in _runs(layouts):
        if layout not in ("title", "section", "closing"):
            out.append(
                f"slides from {first} use the '{layout}' layout {SAME_LAYOUT_RUN} or more times in a row: "
                "vary the layout (a chart, a stat, a two-column or a freeform slide) so the deck has rhythm"
            )
    content = [s for s in deck.slides if not isinstance(s, (TitleSlide, ClosingSlide, SectionSlide))]
    if len(content) >= 4:
        text_only = [s for s in content if isinstance(s, (BulletsSlide, TwoColumnSlide))]
        if len(text_only) / len(content) > TEXT_ONLY_SHARE:
            out.append(
                f"{len(text_only)} of {len(content)} content slides are text only: give most slides a visual "
                "(chart, numbers, table, picture or a drawn diagram) so the deck is not a wall of bullets"
            )
    bars = [n for n, s in enumerate(deck.slides, start=1) if isinstance(s, FreeformSlide) and _accent_bars(s)]
    if bars:
        out.append(
            "slide(s) "
            + ", ".join(map(str, bars))
            + " have a thin accent bar near the title: drop it, it is a "
            "decoration that makes slides look generated"
        )
    return out
