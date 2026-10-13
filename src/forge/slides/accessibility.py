"""Accessibility of a deck (TODO P2.9, D-314): what a screen reader and a colour-blind viewer get. Two parts:

- `check_deck` reads ANY .pptx and lists what is missing: a document title, a slide title, alt text on pictures, charts and tables, a
  header row on tables, the title read before the rest, link text that says nothing, a language, charts whose colours fall together
  for a colour-blind viewer.
- `improve_deck` repairs what can be repaired without guessing: the language on every text run, the document title, reading order
  (title first, footer and slide number last), table header flags, and alt text for charts and tables taken from the slide title.
Colour vision is simulated with the Machado et al. (2009) matrices for protanopia, deuteranopia and tritanopia at full severity."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from forge.slides.colorvision import palette_conflicts
from forge.slides.edit_find import walk
from forge.slides.geometry import Geometry

DEFAULT_LANGUAGE = "en-US"
VAGUE_LINKS = {"click here", "here", "link", "this link", "read more", "more", "this"}
MIN_COLOUR_DELTA = (
    18.0  # CIE76 distance below which two colours are hard to tell apart in a simulated colour-blind view
)
NS_P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
NS_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


@dataclass(frozen=True)
class Problem:
    slide: int | None  # 1-based; None for the deck as a whole
    level: str  # "error" (a reader is blocked) or "warning" (worse than it should be)
    message: str

    def render(self) -> str:
        where = f"slide {self.slide}" if self.slide else "deck"
        return f"{self.level}: {where}: {self.message}"


# --- reading a deck ---


def _runs(slide: Any) -> list[Any]:
    out = []
    for shape in walk(slide.shapes):
        if getattr(shape, "has_text_frame", False) and shape.has_text_frame:
            out += [run for p in shape.text_frame.paragraphs for run in p.runs]
        if getattr(shape, "has_table", False) and shape.has_table:
            out += [
                run
                for row in shape.table.rows
                for cell in row.cells
                for p in cell.text_frame.paragraphs
                for run in p.runs
            ]
    return out


def _description(shape: Any) -> str:
    nodes = shape._element.xpath("(.//p:cNvPr)[1]/@descr")
    return str(nodes[0]).strip() if nodes else ""


def _is_footer_like(shape: Any, slide_height: int, geo: Geometry) -> bool:
    top = geo.box(shape)[1]
    if top is None or not getattr(shape, "has_text_frame", False) or not shape.has_text_frame:
        return False
    text = shape.text_frame.text.strip()
    return top > slide_height * 0.9 and len(text) < 120


def _chart_colours(chart: Any) -> list[str]:
    colours: list[str] = []
    try:
        for series in chart.plots[0].series:
            fill = series.format.fill
            if fill.type is not None and fill.fore_color.type is not None:
                colours.append(str(fill.fore_color.rgb))
    except (AttributeError, ValueError, TypeError, KeyError):
        pass
    return [f"#{c}" for c in colours if re.fullmatch(r"[0-9A-Fa-f]{6}", c)]


def check_deck(prs: Any) -> list[Problem]:
    problems: list[Problem] = []
    geo = Geometry()
    if not (prs.core_properties.title or "").strip():
        problems.append(
            Problem(
                None,
                "error",
                "the document has no title (File > Info > Title): screen readers and the taskbar use it",
            )
        )
    all_runs = 0
    with_language = 0
    for number, slide in enumerate(prs.slides, start=1):
        runs = _runs(slide)
        all_runs += len(runs)
        with_language += sum(1 for r in runs if r._r.rPr is not None and r._r.rPr.get("lang"))
        title = slide.shapes.title
        if title is None or not title.text_frame.text.strip():
            problems.append(
                Problem(number, "error", "has no title: screen reader users navigate by slide titles")
            )
        tree = list(slide.shapes)
        first_text = next(
            (
                s
                for s in tree
                if getattr(s, "has_text_frame", False) and s.has_text_frame and s.text_frame.text.strip()
            ),
            None,
        )
        if (
            title is not None
            and title.text_frame.text.strip()
            and first_text is not None
            and first_text._element is not title._element
        ):
            problems.append(
                Problem(
                    number,
                    "warning",
                    "the title is read after other text: move it first in the reading order",
                )
            )
        footers = [i for i, s in enumerate(tree) if _is_footer_like(s, prs.slide_height, geo)]
        content_after = [
            i
            for i in range(len(tree))
            if footers
            and i > footers[0]
            and i not in footers
            and tree[i].shape_type != 1
            and _has_text(tree[i])
        ]
        if content_after:
            problems.append(
                Problem(number, "warning", "the footer or slide number is read before the slide's content")
            )
        for shape in walk(slide.shapes):
            if shape.shape_type == 13 and not _description(shape):
                problems.append(Problem(number, "error", f"the picture '{shape.name}' has no alt text"))
            elif getattr(shape, "has_chart", False) and shape.has_chart:
                if not _description(shape):
                    problems.append(
                        Problem(
                            number,
                            "warning",
                            f"the chart '{shape.name}' has no alt text describing what it shows",
                        )
                    )
                colours = _chart_colours(shape.chart)
                if len(colours) >= 3:
                    for first, second, kind in palette_conflicts(colours)[:2]:
                        problems.append(
                            Problem(
                                number,
                                "warning",
                                f"chart colours {first} and {second} look alike with {kind}: add direct labels or change a colour",
                            )
                        )
            elif getattr(shape, "has_table", False) and shape.has_table:
                if not _description(shape):
                    problems.append(Problem(number, "warning", f"the table '{shape.name}' has no alt text"))
                if not shape.table.first_row:
                    problems.append(
                        Problem(number, "warning", f"the table '{shape.name}' has no header row marked")
                    )
        for run in runs:
            link = getattr(run.hyperlink, "address", None) if hasattr(run, "hyperlink") else None
            if link and (
                run.text.strip().lower() in VAGUE_LINKS
                or run.text.strip().startswith(("http://", "https://"))
            ):
                problems.append(
                    Problem(
                        number,
                        "warning",
                        f"the link text '{run.text.strip()[:40]}' says nothing about where it goes",
                    )
                )
    if all_runs and with_language / all_runs < 0.9:
        problems.append(
            Problem(None, "warning", "the text has no language set: spell-check and screen readers guess it")
        )
    return problems


def _has_text(shape: Any) -> bool:
    return bool(
        getattr(shape, "has_text_frame", False) and shape.has_text_frame and shape.text_frame.text.strip()
    )


# --- repairing it ---


def improve_deck(prs: Any, language: str = DEFAULT_LANGUAGE, title: str = "") -> list[str]:
    """Repairs what needs no guessing; returns what was done."""
    done: list[str] = []
    geo = Geometry()
    if title and not (prs.core_properties.title or "").strip():
        prs.core_properties.title = title
        done.append("set the document title")
    set_lang = 0
    for slide in prs.slides:
        for run in _runs(slide):
            properties = run._r.get_or_add_rPr()
            if not properties.get("lang"):
                properties.set("lang", language)
                set_lang += 1
    if set_lang:
        done.append(f"set the language ({language}) on {set_lang} text runs")
    reordered = 0
    for slide in prs.slides:
        reordered += _fix_reading_order(slide, prs.slide_height, geo)
        slide_title = slide.shapes.title.text_frame.text.strip() if slide.shapes.title is not None else ""
        for shape in walk(slide.shapes):
            if getattr(shape, "has_chart", False) and shape.has_chart and not _description(shape):
                _set_description(shape, f"Chart: {slide_title}" if slide_title else "Chart")
            elif getattr(shape, "has_table", False) and shape.has_table:
                if not _description(shape):
                    _set_description(shape, f"Table: {slide_title}" if slide_title else "Table")
                if not shape.table.first_row:
                    shape.table.first_row = True
    if reordered:
        done.append(f"fixed the reading order on {reordered} slide(s)")
    return done


def _set_description(shape: Any, text: str) -> None:
    nodes = shape._element.xpath("(.//p:cNvPr)[1]")
    if nodes:
        nodes[0].set("descr", text)


def _overlaps(first: Any, second: Any, geo: Geometry) -> bool:
    a, b = geo.box(first), geo.box(second)
    if None in a or None in b:
        return False
    return not (
        a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]  # type: ignore[operator]
    )


def _fix_reading_order(slide: Any, slide_height: int, geo: Geometry) -> int:
    """The title first and footer-like text last in the reading order. The list is also the drawing order (a later shape is drawn on
    top), so a shape only moves when that cannot change what is seen: the title does not go behind a shape it overlaps, a footer
    does not go on top of a later shape it overlaps."""
    tree = slide.shapes._spTree
    shapes = list(slide.shapes)
    title = slide.shapes.title
    if title is None:
        return 0
    order = list(shapes)
    moved = False
    position = next(i for i, s in enumerate(order) if s._element is title._element)
    if position > 0 and not any(_overlaps(s, title, geo) for s in order[:position]):
        order.insert(0, order.pop(position))
        moved = True
    for shape in [
        s for s in list(order) if s._element is not title._element and _is_footer_like(s, slide_height, geo)
    ]:
        index = next(i for i, s in enumerate(order) if s._element is shape._element)
        later = order[index + 1 :]
        if later and not any(_overlaps(shape, s, geo) for s in later):
            order.append(order.pop(index))
            moved = True
    if not moved:
        return 0
    anchors = tree.xpath("./p:grpSpPr")
    for shape in order:
        tree.remove(shape._element)
    start = list(tree).index(anchors[0]) + 1 if anchors else 0
    for offset, shape in enumerate(order):
        tree.insert(start + offset, shape._element)
    return 1
