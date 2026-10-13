"""Review mode (TODO P2.17, D-318): a critique of ANY .pptx, with what to do about each finding. The checks are deterministic (no model
involved), so the same deck always gets the same review; the model decides which findings matter and fixes them with the edit tools.

Areas: story (titles that say something, no repeats), density (words per slide, long bullets), consistency (fonts, sizes, title
positions), contrast, layout (repeated layouts, text-only runs, shapes off the slide or on top of each other), speaker notes, empty
placeholders, and the accessibility findings of P2.9."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from forge.slides.accessibility import check_deck
from forge.slides.edit_find import walk
from forge.slides.themes import contrast

MAX_WORDS_ON_SLIDE = 90
MAX_BULLETS_IN_BOX = 7
MAX_WORDS_IN_BULLET = 24
MAX_TITLE_WORDS = 14
LABEL_TITLE_WORDS = 2
MAX_FONT_FAMILIES = 2
MAX_FONT_SIZES = 7
MIN_POINTS = 12
SAME_LAYOUT_RUN = 4
TITLE_DRIFT_INCHES = 0.1
TEXT_ONLY_SHARE = 0.7
EMU = 914400
GENERIC_TITLES = {
    "overview",
    "introduction",
    "agenda",
    "summary",
    "details",
    "content",
    "background",
    "update",
    "next steps",
    "thank you",
    "questions",
}
CHROME = {"FOOTER", "SLIDE_NUMBER", "DATE"}


@dataclass(frozen=True)
class Finding:
    area: str
    level: str  # "problem" (fix it) or "suggestion" (worth a look)
    slide: int | None
    message: str
    fix: str

    def render(self) -> str:
        where = f"slide {self.slide}" if self.slide else "deck"
        return f"[{self.area}] {self.level}: {where}: {self.message} -> {self.fix}"


def _words(text: str) -> int:
    return len(re.findall(r"\w+", text))


def _is_chrome(shape: Any) -> bool:
    return bool(shape.is_placeholder and shape.placeholder_format.type.name in CHROME)


def _text_frames(slide: Any) -> list[Any]:
    return [
        s
        for s in walk(slide.shapes)
        if getattr(s, "has_text_frame", False)
        and s.has_text_frame
        and s.text_frame.text.strip()
        and not _is_chrome(s)
    ]


def _runs(slide: Any) -> list[Any]:
    return [r for s in _text_frames(slide) for p in s.text_frame.paragraphs for r in p.runs if r.text.strip()]


def _rgb(color: Any) -> str | None:
    try:
        return str(color.rgb) if color.type is not None and color.rgb is not None else None
    except (AttributeError, ValueError, TypeError):
        return None


def _solid(fill: Any) -> str | None:
    try:
        return _rgb(fill.fore_color) if fill.type == 1 else None
    except (AttributeError, ValueError, TypeError, KeyError):
        return None


def _behind(slide: Any, shape: Any) -> str | None:
    """The solid fill of the shape the text sits in, or of the last filled shape under it, else the slide background."""
    try:
        own = _solid(shape.fill)
    except (AttributeError, ValueError, TypeError, KeyError):
        own = None
    if own:
        return own
    colour = _solid(slide.background.fill)
    for other in slide.shapes:
        if other._element is shape._element:
            break
        try:
            covers = (
                other.left <= shape.left
                and other.top <= shape.top
                and other.left + other.width >= shape.left + shape.width
                and other.top + other.height >= shape.top + shape.height
            )
            if covers and not (getattr(other, "has_text_frame", False) and other.text_frame.text.strip()):
                colour = _solid(other.fill) or colour
        except (AttributeError, ValueError, TypeError, KeyError):
            continue
    return colour


def review_deck(prs: Any, minutes: int | None = None) -> list[Finding]:
    findings: list[Finding] = []
    slides = list(prs.slides)
    titles: list[tuple[int, str]] = []
    for number, slide in enumerate(slides, start=1):
        title_shape = slide.shapes.title
        title_element = title_shape._element if title_shape is not None else None
        title = title_shape.text_frame.text.strip() if title_shape is not None else ""
        if title:
            titles.append((number, title))
        words = _words(title)
        at_edge = number in (1, len(slides))
        if (
            title
            and not at_edge
            and (words <= LABEL_TITLE_WORDS or title.lower().rstrip(".") in GENERIC_TITLES)
        ):
            findings.append(
                Finding(
                    "story",
                    "suggestion",
                    number,
                    f"the title '{title}' is a label, not a message",
                    "rewrite it as the point of the slide (a sentence with a verb)",
                )
            )
        if words > MAX_TITLE_WORDS:
            findings.append(
                Finding(
                    "story",
                    "problem",
                    number,
                    f"the title has {words} words",
                    "shorten it to one line of at most about 12 words",
                )
            )
        frames = _text_frames(slide)
        body_words = sum(_words(s.text_frame.text) for s in frames if s._element is not title_element)
        if body_words > MAX_WORDS_ON_SLIDE:
            findings.append(
                Finding(
                    "density",
                    "problem",
                    number,
                    f"{body_words} words on the slide",
                    "move detail to the speaker notes or split the slide in two",
                )
            )
        for shape in frames:
            if shape._element is title_element:
                continue
            paragraphs = [p for p in shape.text_frame.paragraphs if p.text.strip()]
            if len(paragraphs) > MAX_BULLETS_IN_BOX:
                findings.append(
                    Finding(
                        "density",
                        "problem",
                        number,
                        f"{len(paragraphs)} bullets in one box",
                        "keep 3 to 5, group the rest or use a table",
                    )
                )
            long = next((p for p in paragraphs if _words(p.text) > MAX_WORDS_IN_BULLET), None)
            if long is not None:
                findings.append(
                    Finding(
                        "density",
                        "suggestion",
                        number,
                        f"a paragraph of {_words(long.text)} words: '{long.text[:40]}...'",
                        "cut it to one short line",
                    )
                )
        findings.extend(_slide_geometry(prs, slide, number))
        findings.extend(_slide_contrast(slide, number))
        for shape in slide.shapes:
            if (
                shape.is_placeholder
                and getattr(shape, "has_text_frame", False)
                and shape.has_text_frame
                and not shape.text_frame.text.strip()
                and not _is_chrome(shape)
            ):
                findings.append(
                    Finding(
                        "layout",
                        "problem",
                        number,
                        f"the empty placeholder '{shape.name}' shows 'Click to add text' when editing",
                        "fill it or run remove_empty_placeholders",
                    )
                )
        has_notes = slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip()
        if not at_edge and not has_notes:
            findings.append(
                Finding(
                    "notes", "suggestion", number, "no speaker notes", "add what the speaker says (set_notes)"
                )
            )
    counts = Counter(t.lower() for _, t in titles)
    for number, title in titles:
        if counts[title.lower()] > 1 and number > 1:
            findings.append(
                Finding(
                    "story",
                    "problem",
                    number,
                    f"the title '{title}' is used on {counts[title.lower()]} slides",
                    "give each slide its own message",
                )
            )
    findings.extend(_deck_consistency(slides))
    findings.extend(_deck_rhythm(slides))
    content = max(len(slides) - 2, 1)
    if minutes and content > minutes:
        findings.append(
            Finding(
                "story",
                "suggestion",
                None,
                f"{content} content slides for {minutes} minutes is more than one slide a minute",
                "cut slides or move some to an appendix (hide_slide)",
            )
        )
    for problem in check_deck(prs):
        findings.append(
            Finding(
                "accessibility",
                "problem" if problem.level == "error" else "suggestion",
                problem.slide,
                problem.message,
                "see check_accessibility; build_presentation repairs most of these",
            )
        )
    return findings


def _slide_geometry(prs: Any, slide: Any, number: int) -> list[Finding]:
    found: list[Finding] = []
    width, height = prs.slide_width, prs.slide_height
    slack = EMU // 20
    boxes = [s for s in _text_frames(slide) if None not in (s.left, s.top, s.width, s.height)]
    for shape in slide.shapes:
        if None in (shape.left, shape.top, shape.width, shape.height) or _is_chrome(shape):
            continue
        if (
            shape.left < -slack
            or shape.top < -slack
            or shape.left + shape.width > width + slack
            or shape.top + shape.height > height + slack
        ):
            found.append(
                Finding(
                    "layout",
                    "problem",
                    number,
                    f"'{shape.name}' reaches past the edge of the slide",
                    "move or resize it inside the slide",
                )
            )
    for index, first in enumerate(boxes):
        for second in boxes[index + 1 :]:
            overlap_w = min(first.left + first.width, second.left + second.width) - max(
                first.left, second.left
            )
            overlap_h = min(first.top + first.height, second.top + second.height) - max(first.top, second.top)
            if overlap_w <= EMU * 0.1 or overlap_h <= EMU * 0.1:
                continue
            share = overlap_w * overlap_h / min(first.width * first.height, second.width * second.height)
            if share > 0.25:
                found.append(
                    Finding(
                        "layout",
                        "problem",
                        number,
                        f"the text boxes '{first.name}' and '{second.name}' overlap",
                        "move one of them or shorten the text",
                    )
                )
    return found


def _slide_contrast(slide: Any, number: int) -> list[Finding]:
    for shape in _text_frames(slide):
        background = _behind(slide, shape)
        if not background:
            continue
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:
                colour = _rgb(run.font.color) if run.text.strip() else None
                if not colour:
                    continue
                size = run.font.size.pt if run.font.size else 18
                needed = 3.0 if size >= 24 or (size >= 18.5 and run.font.bold) else 4.5
                ratio = contrast(colour.upper(), background.upper())
                if ratio < needed:  # one per slide is enough to act on
                    return [
                        Finding(
                            "contrast",
                            "problem",
                            number,
                            f"text '{run.text.strip()[:30]}' is {ratio:.1f}:1 against its background (needs {needed})",
                            "use a darker or lighter text colour",
                        )
                    ]
    return []


def _deck_consistency(slides: list[Any]) -> list[Finding]:
    found: list[Finding] = []
    families: Counter[str] = Counter()
    sizes: Counter[float] = Counter()
    small: dict[int, float] = {}
    for number, slide in enumerate(slides, start=1):
        for run in _runs(slide):
            if run.font.name:
                families[run.font.name] += 1
            if run.font.size:
                sizes[run.font.size.pt] += 1
                if run.font.size.pt < MIN_POINTS:
                    small[number] = min(small.get(number, 99.0), run.font.size.pt)
    if len(families) > MAX_FONT_FAMILIES:
        found.append(
            Finding(
                "consistency",
                "problem",
                None,
                f"{len(families)} font families: {', '.join(sorted(families))}",
                "use one for titles and one for text (set_theme heading_font/body_font, format_text font)",
            )
        )
    if len(sizes) > MAX_FONT_SIZES:
        found.append(
            Finding(
                "consistency",
                "suggestion",
                None,
                f"{len(sizes)} different text sizes",
                "keep to a scale of about five sizes",
            )
        )
    for number, points in small.items():
        found.append(
            Finding(
                "consistency",
                "problem",
                number,
                f"text as small as {points:g} pt",
                f"{MIN_POINTS} pt is the least that reads from a seat in the room: enlarge or cut text",
            )
        )
    spots = [
        (number, slide.shapes.title.left, slide.shapes.title.top)
        for number, slide in enumerate(slides, start=1)
        if number not in (1, len(slides))
        and slide.shapes.title is not None
        and slide.shapes.title.left is not None
    ]
    if spots:
        usual_left = Counter(left for _, left, _ in spots).most_common(1)[0][0]
        usual_top = Counter(top for _, _, top in spots).most_common(1)[0][0]
        drift = EMU * TITLE_DRIFT_INCHES
        found.extend(
            Finding(
                "consistency",
                "problem",
                number,
                "the title is not where it is on most slides",
                "move it to the usual place (the layout's title position)",
            )
            for number, left, top in spots
            if abs(left - usual_left) > drift or abs(top - usual_top) > drift
        )
    return found


def _deck_rhythm(slides: list[Any]) -> list[Finding]:
    found: list[Finding] = []
    run, previous = 0, ""
    for number, slide in enumerate(slides, start=1):
        name = slide.slide_layout.name
        run = run + 1 if name == previous else 1
        previous = name
        if run == SAME_LAYOUT_RUN:
            found.append(
                Finding(
                    "layout",
                    "suggestion",
                    number,
                    f"{SAME_LAYOUT_RUN} slides in a row use the layout '{name}'",
                    "break the run with a chart, a picture, a quote or a section slide",
                )
            )
    text_only = [
        n
        for n, s in enumerate(slides, start=1)
        if not any(
            sh.shape_type == 13 or getattr(sh, "has_chart", False) or getattr(sh, "has_table", False)
            for sh in walk(s.shapes)
        )
    ]
    if len(slides) >= 6 and len(text_only) / len(slides) > TEXT_ONLY_SHARE:
        found.append(
            Finding(
                "layout",
                "suggestion",
                None,
                f"{len(text_only)} of {len(slides)} slides have only text",
                "turn some into a chart, table, diagram or picture",
            )
        )
    return found


def summarize(findings: list[Finding], limit: int = 60) -> str:
    if not findings:
        return "Review: no findings. (Deterministic checks only; still look at the slide pictures.)"
    problems = [f for f in findings if f.level == "problem"]
    ranked = sorted(findings, key=lambda f: (f.level != "problem", f.slide or 0))
    lines = [f"Review: {len(problems)} problem(s), {len(findings) - len(problems)} suggestion(s)."]
    lines += [f.render() for f in ranked[:limit]]
    if len(ranked) > limit:
        lines.append(f"... and {len(ranked) - limit} more")
    return "\n".join(lines)
