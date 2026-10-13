"""The sample slides of a corporate template (TODO P2.21, D-290). A company template usually carries ready-made slides: a title
slide, an agenda, three cards in a row, a big-number slide, a thank-you slide. Their look is the corporate look, so DebCraft reuses
them: each sample is described by its slots (the text shapes with the words they hold now), the repeated groups (the cards, steps
or columns), what kind of slide it is, and what is fixed (logo text, footers repeated on every sample). `fill_sample` then
puts new content into a copy of the sample and removes every word of the sample that was not replaced.

Slots are named so the model can fill them from the description: `title`, `subtitle`, `body`, `items` (the repeated groups: each
item has `number`, `heading`, `text` where the sample has them) and `slot:<shape id>` for anything else."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from forge.slides.edit_find import walk
from forge.slides.edit_text import set_frame_text

EMU = 914400
FOOTER_KINDS = {"DATE", "FOOTER", "SLIDE_NUMBER"}
THANKS = re.compile(r"thank|questions|contact|discussion", re.I)
# Notes the template author left on the sample slide for the person who copies it ("Delete before using ...", seen on a real company template):
# never content, never offered as a slot, always removed from the copy.
INSTRUCTION = re.compile(
    r"^\W*(delete\s+(this\s+)?before\s+(using|you\s+use)|delete\s+this|remove\s+before\s+(using|use)|instructions?\s*:|note\s+to\s+(author|designer)s?)",
    re.I,
)
NUMBERISH = re.compile(r"^[\d.,+\-–%$€£kKmMbB x/]{1,12}$")  # noqa: RUF001  (the en dash is meant)
STEP_NUMBER = re.compile(r"^(0?\d|[ivx]+)[.)]?$", re.I)
QUOTE_MARKS = ("“", '"', "«")


@dataclass
class Slot:
    id: int
    name: str  # the shape's own name
    role: str  # title, subtitle, body, number, heading, text, picture
    text: str
    x: float
    y: float
    w: float
    h: float
    size_pt: float | None
    paragraphs: int
    fixed: bool = False  # the same on most samples (a footer, a company line): never touched


@dataclass
class Item:
    """One repeated group (a card, a step, a column): its slots by part, and the shapes that belong to it."""

    parts: dict[str, Slot]
    slots: list[Slot]
    x: float
    y: float
    w: float
    h: float


@dataclass
class Sample:
    number: int  # 1-based slide number in the template
    layout: str
    kind: str
    slots: list[Slot]
    items: list[Item] = field(default_factory=list)
    pictures: int = 0
    charts: int = 0
    tables: int = 0

    def slot(self, role: str) -> Slot | None:
        return next((s for s in self.slots if s.role == role and not s.fixed and not self._in_items(s)), None)

    def _in_items(self, slot: Slot) -> bool:
        return any(slot in item.slots for item in self.items)


# --- reading ---


def _size(shape: Any) -> float | None:
    sizes = [
        run.font.size.pt
        for p in shape.text_frame.paragraphs
        for run in p.runs
        if run.font.size is not None and run.text.strip()
    ]
    return max(sizes) if sizes else None


def _placeholder_kind(shape: Any) -> str | None:
    try:
        kind = shape.placeholder_format.type
    except (ValueError, AttributeError):
        return None
    return kind.name if kind is not None else None


def _role(shape: Any, text: str, size: float | None, top_rank: int) -> str:
    kind = _placeholder_kind(shape)
    if kind in ("TITLE", "CENTER_TITLE"):
        return "title"
    if kind == "SUBTITLE":
        return "subtitle"
    if kind in ("BODY", "OBJECT"):
        return "body"
    if NUMBERISH.match(text.strip()) and (size or 0) >= 28:
        return "number"
    if STEP_NUMBER.match(text.strip()):
        return "number"
    if top_rank == 0 and (size or 0) >= 24 and len(text.split()) <= 14:
        return "title"
    return "text"


def is_instruction(shape: Any) -> bool:
    """A shape (or a group holding one) whose text is an instruction to the template's user."""
    if (
        getattr(shape, "has_text_frame", False)
        and shape.has_text_frame
        and INSTRUCTION.match(shape.text_frame.text.strip())
    ):
        return True
    if shape.shape_type == 6:
        return any(is_instruction(child) for child in shape.shapes)
    return False


def remove_instructions(slide: Any) -> int:
    """Removes the instruction notes from a copy of a sample slide; returns how many."""
    doomed = [s for s in slide.shapes if is_instruction(s)]
    for shape in doomed:
        _remove(shape)
    return len(doomed)


def _slots_of(slide: Any) -> tuple[list[Slot], int, int, int]:
    pictures = charts = tables = 0
    found: list[tuple[Any, str]] = []
    notes = [
        e for s in slide.shapes if is_instruction(s) for e in s._element.iter()
    ]  # the note and everything inside it
    hidden = {id(e) for e in notes}  # `notes` keeps the elements alive, so no id is reused
    for shape in walk(slide.shapes):
        if id(shape._element) in hidden:
            continue
        if shape.shape_type == 13 or _placeholder_kind(shape) == "PICTURE":
            pictures += 1
        if getattr(shape, "has_chart", False) and shape.has_chart:
            charts += 1
        if getattr(shape, "has_table", False) and shape.has_table:
            tables += 1
        if getattr(shape, "has_text_frame", False) and shape.has_text_frame and shape.text_frame.text.strip():
            found.append((shape, shape.text_frame.text.strip()))
    ordered = sorted(found, key=lambda pair: (pair[0].top or 0, pair[0].left or 0))
    slots: list[Slot] = []
    for rank, (shape, text) in enumerate(ordered):
        size = _size(shape)
        slots.append(
            Slot(
                id=shape.shape_id,
                name=shape.name,
                role=_role(shape, text, size, rank),
                text=text,
                x=(shape.left or 0) / EMU,
                y=(shape.top or 0) / EMU,
                w=(shape.width or 0) / EMU,
                h=(shape.height or 0) / EMU,
                size_pt=size,
                paragraphs=len(shape.text_frame.paragraphs),
                fixed=_placeholder_kind(shape) in FOOTER_KINDS,
            )
        )
    return slots, pictures, charts, tables


def _similar(a: Slot, b: Slot) -> bool:
    return abs(a.w - b.w) <= 0.15 * max(a.w, b.w) and abs(a.h - b.h) <= 0.25 * max(a.h, b.h, 0.1)


def _items(slots: list[Slot], width: float, height: float) -> list[Item]:
    """Repeated groups: columns (or rows) of slots that share a shape. Needs two or more of them with the same parts."""
    candidates = [s for s in slots if s.role in ("number", "heading", "text", "body") and not s.fixed]
    for axis in ("x", "y"):
        buckets: list[list[Slot]] = []
        for slot in sorted(candidates, key=lambda s: (getattr(s, axis), s.y if axis == "x" else s.x)):
            span = slot.w if axis == "x" else slot.h
            for bucket in buckets:
                anchor = bucket[0]
                if abs(getattr(anchor, axis) - getattr(slot, axis)) <= 0.5 * max(span, 0.3) and _similar_axis(
                    anchor, slot, axis
                ):
                    bucket.append(slot)
                    break
            else:
                buckets.append([slot])
        if len(buckets) >= 2 and len({len(b) for b in buckets}) == 1 and len(buckets[0]) <= 4:
            return [_item(bucket) for bucket in buckets]
    return []


def _similar_axis(a: Slot, b: Slot, axis: str) -> bool:
    return (
        abs(a.w - b.w) <= 0.25 * max(a.w, b.w) if axis == "x" else abs(a.h - b.h) <= 0.5 * max(a.h, b.h, 0.1)
    )


def _item(bucket: list[Slot]) -> Item:
    ordered = sorted(bucket, key=lambda s: (s.y, s.x))
    parts: dict[str, Slot] = {}
    for slot in ordered:
        role = slot.role
        if (
            role == "text"
            and "heading" not in parts
            and len(ordered) > 1
            and slot is ordered[0 if not any(s.role == "number" for s in ordered) else 1]
        ):
            role = "heading"
        if role == "body":
            role = "text"
        parts.setdefault(role, slot)
    x0, y0 = min(s.x for s in bucket), min(s.y for s in bucket)
    x1, y1 = max(s.x + s.w for s in bucket), max(s.y + s.h for s in bucket)
    return Item(parts, ordered, x0, y0, x1 - x0, y1 - y0)


def _kind(
    layout_role: str,
    slots: list[Slot],
    items: list[Item],
    pictures: int,
    charts: int,
    tables: int,
    last: bool,
) -> str:
    texts = " ".join(s.text for s in slots)
    if charts:
        return "chart"
    if tables:
        return "table"
    if layout_role == "title" and not last:
        return "title"
    if layout_role == "section":
        return "section"
    if pictures and slots:
        return "image_text"
    if items:
        if any(
            "number" in item.parts
            and NUMBERISH.match(item.parts["number"].text.strip())
            and (item.parts["number"].size_pt or 0) >= 28
            for item in items
        ):
            return "stats"
        if all(
            STEP_NUMBER.match(item.parts["number"].text.strip()) for item in items if "number" in item.parts
        ) and any("number" in i.parts for i in items):
            return "steps"
        return "two_column" if len(items) == 2 else "cards"
    if any(texts.lstrip().startswith(mark) for mark in QUOTE_MARKS) or any(
        s.text.startswith(QUOTE_MARKS) for s in slots
    ):
        return "quote"
    if THANKS.search(texts) and len(texts.split()) <= 25:
        return "thanks"
    if layout_role == "title":
        return "title"
    body = next((s for s in slots if s.role == "body" or (s.role == "text" and s.paragraphs >= 3)), None)
    if body is not None and body.paragraphs >= 2:
        return "bullets"
    return "other"


def analyze_samples(prs: Any) -> list[Sample]:
    """Every slide of the template as a Sample (an empty list when the template has no slides)."""
    from forge.slides.template import classify_layout

    slides = list(prs.slides)
    read = [_slots_of(slide) for slide in slides]
    texts = [{s.text for s in slots} for slots, *_ in read]
    if (
        len(slides) >= 3
    ):  # text that repeats on most samples is the company's own (a footer line, a confidentiality note)
        for slots, *_ in read:
            for slot in slots:
                if (
                    sum(1 for t in texts if slot.text in t) >= max(2, len(slides) // 2 + 1)
                    and slot.role != "title"
                ):
                    slot.fixed = True
    samples: list[Sample] = []
    for number, (slide, (slots, pictures, charts, tables)) in enumerate(
        zip(slides, read, strict=True), start=1
    ):
        role, _ = classify_layout(slide.slide_layout)
        items = _items(slots, prs.slide_width / EMU, prs.slide_height / EMU)
        kind = _kind(
            role, [s for s in slots if not s.fixed], items, pictures, charts, tables, number == len(slides)
        )
        samples.append(Sample(number, slide.slide_layout.name, kind, slots, items, pictures, charts, tables))
    return samples


# --- describing ---


def describe_samples(samples: list[Sample]) -> str:
    """The samples as text for the model: kind, slots with their current words, and how to fill each."""
    if not samples:
        return "The template has no sample slides: slides are made from its layouts."
    lines = [
        f"Sample slides ({len(samples)}). Use one with {{layout: template_slide, source: N, fill: {{...}}}}:"
    ]
    for sample in samples:
        lines.append(f'  Slide {sample.number} [{sample.kind}] layout "{sample.layout}"')
        for slot in sample.slots:
            if slot.fixed or any(slot in item.slots for item in sample.items):
                continue
            lines.append(
                f"    {slot.role}: {slot.text[:60]!r}"
                + (f" ({slot.paragraphs} paragraphs)" if slot.paragraphs > 1 else "")
            )
        if sample.items:
            parts = "/".join(sample.items[0].parts)
            shown = "; ".join(repr(" ".join(s.text for s in item.slots)[:30]) for item in sample.items)
            lines.append(f"    items: {len(sample.items)} groups, each with {parts}: {shown}")
        extras = [
            f"{n} {name}"
            for n, name in (
                (sample.pictures, "picture(s)"),
                (sample.charts, "chart(s)"),
                (sample.tables, "table(s)"),
            )
            if n
        ]
        if extras:
            lines.append("    also holds " + ", ".join(extras))
    return "\n".join(lines)


# --- filling ---


def _remove(shape: Any) -> None:
    parent = shape._element.getparent()
    if parent is not None:
        parent.remove(shape._element)


def _lines(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return str(value).split("\n")


def _shape_by_id(slide: Any, shape_id: int) -> Any | None:
    return next((s for s in walk(slide.shapes) if s.shape_id == shape_id), None)


def _set(slide: Any, slot: Slot, value: Any) -> None:
    shape = _shape_by_id(slide, slot.id)
    if shape is not None:
        set_frame_text(shape.text_frame, _lines(value))


KEY_ALIASES = {
    "bullets": "body", "points": "body", "content": "body", "paragraphs": "body", "lines": "body", "list": "body",
    "heading": "title", "headline": "title", "name": "title",
    "subheading": "subtitle", "tagline": "subtitle",
}  # fmt: skip
PART_ALIASES = {
    "value": "number", "figure": "number", "stat": "number", "metric": "number", "count": "number", "index": "number",
    "label": "heading", "title": "heading", "name": "heading", "header": "heading", "headline": "heading",
    "description": "text", "body": "text", "detail": "text", "details": "text", "caption": "text", "content": "text", "subtitle": "text",
}  # fmt: skip
PART_FALLBACK = {"number": ("heading", "text"), "heading": ("text",), "text": ("heading",)}


def _part_for(name: str, item: Item) -> str | None:
    """The part of an item a content name belongs to: the name itself, a common synonym, or the nearest part the sample has."""
    wanted = name if name in item.parts else PART_ALIASES.get(name, name)
    if wanted in item.parts:
        return wanted
    return next((p for p in PART_FALLBACK.get(wanted, ()) if p in item.parts), None)


def _item_values(value: Any, item: Item) -> tuple[dict[str, str], list[str]]:
    """Content of one item by part, and the names that fitted no part (their content would be lost)."""
    if not isinstance(value, dict):
        target = (
            "heading"
            if "heading" in item.parts
            else "text"
            if "text" in item.parts
            else next(iter(item.parts))
        )
        return {target: str(value)}, []
    values: dict[str, str] = {}
    lost: list[str] = []
    for key, content in value.items():
        if content in (None, ""):
            continue
        part = _part_for(key, item)
        if part is None or part in values:
            lost.append(key)
        else:
            values[part] = str(content)
    return values, lost


def _shapes_inside(slide: Any, item: Item, margin: float = 0.3) -> list[Any]:
    """Shapes (a card background, a number circle) whose centre lies within the item's area."""
    found = []
    for shape in slide.shapes:
        if shape.left is None or shape.width is None:
            continue
        cx, cy = (shape.left + shape.width / 2) / EMU, (shape.top + shape.height / 2) / EMU
        inside = (
            item.x - margin <= cx <= item.x + item.w + margin
            and item.y - margin <= cy <= item.y + item.h + margin
        )
        if (
            inside and shape.width / EMU < item.w * 2.5 and shape.height / EMU < item.h * 2.5
        ):  # not a full-slide panel
            found.append(shape)
    return found


def _centre_kept(slide: Any, items: list[Item], kept: int) -> None:
    """Items standing in a row: after the spare ones are removed, move the kept ones so the row is centred as it was."""
    if kept == 0 or max(i.y for i in items) - min(i.y for i in items) > 0.3:
        return
    before = (min(i.x for i in items) + max(i.x + i.w for i in items)) / 2
    after = (min(i.x for i in items[:kept]) + max(i.x + i.w for i in items[:kept])) / 2
    shift = int((before - after) * EMU)
    moved: set[int] = set()
    for item in items[:kept]:
        for shape in [*(_shape_by_id(slide, s.id) for s in item.slots), *_shapes_inside(slide, item)]:
            if shape is not None and shape.shape_id not in moved and shape.left is not None:
                shape.left += shift
                moved.add(shape.shape_id)


def fill_sample(slide: Any, sample: Sample, fills: dict[str, Any]) -> list[str]:
    """Put the content into a copy of the sample slide; returns problems (slots asked for that the sample does not have).
    Anything of the sample's own text that is not replaced is removed, so no placeholder wording is left behind."""
    problems: list[str] = []
    used: set[int] = set()
    remove_instructions(slide)
    for key, value in {
        KEY_ALIASES.get(k, k) if not k.startswith("slot:") else k: v for k, v in fills.items()
    }.items():
        if key == "items":
            wanted = value if isinstance(value, list) else [value]
            if not sample.items:
                problems.append("this sample has no repeated groups: use body or slot:<id>")
                continue
            if len(wanted) > len(sample.items):
                problems.append(
                    f"this sample has {len(sample.items)} groups, {len(wanted)} items were given: split or merge"
                )
                wanted = wanted[: len(sample.items)]
            for item, content in zip(sample.items, wanted, strict=False):
                values, lost = _item_values(content, item)
                for part, slot in item.parts.items():
                    if part in values:
                        _set(slide, slot, values[part])
                        used.add(slot.id)
                for name in lost:
                    problems.append(
                        f"an item has no place for {name!r}: its parts are {', '.join(item.parts)} (the content would be lost)"
                    )
            for item in sample.items[
                len(wanted) :
            ]:  # fewer items than groups: the spare groups go, with their backgrounds
                for slot in item.slots:
                    used.add(slot.id)
                    shape = _shape_by_id(slide, slot.id)
                    if shape is not None:
                        _remove(shape)
                for shape in _shapes_inside(slide, item):
                    if not getattr(shape, "has_text_frame", False) or not shape.text_frame.text.strip():
                        _remove(shape)
            if len(wanted) < len(sample.items):
                _centre_kept(slide, sample.items, len(wanted))
            continue
        target: Slot | None
        if key.startswith("slot:"):
            target = next((s for s in sample.slots if str(s.id) == key[5:]), None)
        else:
            target = sample.slot(key)
        if target is None:
            problems.append(
                f"this sample has no {key!r} (it has: {', '.join(sorted({s.role for s in sample.slots if not s.fixed}))})"
            )
            continue
        _set(slide, target, value)
        used.add(target.id)
    for slot in sample.slots:  # sample words that nothing replaced must not stay
        if slot.id not in used and not slot.fixed:
            shape = _shape_by_id(slide, slot.id)
            if shape is not None:
                _remove(shape)
    return problems
