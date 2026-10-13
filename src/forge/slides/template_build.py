"""Building a deck on a company template (TODO P2.10, D-288). The outline names the template (`"template": "templates/company.potx"`);
the builder opens it, drops its sample slides, and maps DebCraft's layouts onto the template's own layouts:

- title, closing: the template's title layout (title and subtitle placeholders)
- section: its section header layout
- bullets: its title-and-content layout (the text goes into the body placeholder and inherits the template's bullets, fonts, sizes)
- two_column: its two-content layout
- chart, table, image, stats, quote, freeform: its title-only layout, with the content drawn in the free area under the title,
  coloured from the template's theme (its accent colours become the chart colours; its fonts are used for any text we add)

Anything the template lacks falls back to a title-only layout. Widescreen (16:9) templates of any size are supported by scaling
DebCraft's 13.33 x 7.5 in canvas; other shapes are refused with a clear message."""

from __future__ import annotations

import io
from copy import deepcopy
from typing import Any

from forge.slides import fit
from forge.slides.build import (
    MAX_BULLET_WORDS,
    MAX_BULLETS,
    MIN_BODY_PT,
    SlideReport,
    _Builder,
)
from forge.slides.edit import _duplicate
from forge.slides.edit_find import walk
from forge.slides.errors import BuildError
from forge.slides.open_deck import DeckError
from forge.slides.spec import (
    BulletsSlide,
    CardsSlide,
    ClosingSlide,
    Column,
    Deck,
    QuoteSlide,
    SectionSlide,
    StatsSlide,
    StepsSlide,
    TemplateSlide,
    TitleSlide,
    TwoColumnSlide,
)
from forge.slides.template import TemplateInfo, analyze_template, content_box, theme_from_template
from forge.slides.template_samples import Sample, analyze_samples, fill_sample
from forge.slides.themes import Brand, Theme, apply_brand

BODY_KINDS = ("OBJECT", "BODY")
TITLE_KINDS = ("TITLE", "CENTER_TITLE")
FALLBACK_ROLES = ("title_only", "content", "blank")


def _open(data: bytes) -> Any:
    import zipfile

    from pptx import Presentation

    try:
        return Presentation(io.BytesIO(data))
    except Exception:
        try:
            from forge.slides.open_deck import _as_presentation  # a .potx has another content type

            return Presentation(io.BytesIO(_as_presentation(data)))
        except (zipfile.BadZipFile, KeyError, ValueError) as error:
            raise BuildError(
                "the template could not be opened: is it a damaged or password-protected file?"
            ) from error


def _relationship_free(element: Any) -> bool:
    """True when a shape refers to no picture, link or embedded part (so it can be copied between slides as it is)."""
    return not any("relationships" in key for node in element.iter() for key in node.attrib)


def _signature(shape: Any) -> tuple[Any, ...]:
    return (str(shape.shape_type), shape.name, shape.left, shape.top, shape.width, shape.height)


def _common_decor(prs: Any, samples: list[Sample]) -> list[Any]:
    """Plain shapes (a company line, a coloured bar) that sit in the same place on most sample slides: the template's own
    decoration, which a slide made from a layout should carry too."""
    slides = list(prs.slides)
    if len(slides) < 3:
        return []
    counts: dict[tuple[Any, ...], int] = {}
    first: dict[tuple[Any, ...], Any] = {}
    for slide in slides:
        for shape in slide.shapes:
            if shape.is_placeholder or shape.left is None or not _relationship_free(shape._element):
                continue
            key = _signature(shape)
            counts[key] = counts.get(key, 0) + 1
            first.setdefault(key, shape._element)
    wanted = max(2, len(slides) // 2 + 1)
    return [first[key] for key, count in counts.items() if count >= wanted]


class TemplateBuilder(_Builder):
    def __init__(self, deck: Deck, read_image: Any, template: bytes) -> None:
        self.template_bytes = template
        self.info: TemplateInfo | None = None
        self.samples: list[Sample] = []
        self.sample_count = (
            0  # the template's own slides stay at the front while we copy from them; finish() removes them
        )
        self.decor: list[Any] = []
        self.used_samples: dict[str, int] = {}
        self.read_image = read_image
        super().__init__(deck, read_image)

    # --- set-up: the template decides the theme, the size and the free area ---

    def choose_theme(self) -> Theme:
        prs = _open(self.template_bytes)
        info = analyze_template(prs)
        if not info.widescreen:
            raise BuildError(
                f"the template is {info.width:.1f} x {info.height:.1f} in, not widescreen 16:9: building a new deck on it is not "
                "supported; use a 16:9 template, or edit the template itself with edit_presentation"
            )
        self.info = info
        scale = info.scale
        from pptx.util import Inches, Pt

        self.m = {**self.m, "inches": lambda v: Inches(v * scale), "pt": lambda v: Pt(v * scale)}
        self.scale = scale
        x, y, w, h = content_box(info)
        self.margin, self.content_width = x, w
        self.body_top, self.body_bottom = y, y + h
        layout = info.layouts[info.roles["title_only"]] if "title_only" in info.roles else None
        title = next((p for p in layout.placeholders if p.kind in TITLE_KINDS), None) if layout else None
        if title is not None:
            self.title_top, self.title_height = title.y / scale, title.h / scale
        theme, _, _ = theme_from_template(prs)
        if self.deck.brand is not None:
            kit = {
                key: value.lstrip("#").upper() if key not in ("title_font", "body_font") else value
                for key, value in self.deck.brand.model_dump(exclude_none=True).items()
            }
            theme, self.brand_problems = apply_brand(theme, Brand(**kit))
        return theme

    def make_presentation(self) -> Any:
        prs = _open(self.template_bytes)
        self.samples = analyze_samples(prs)  # kept in the file until finish(): new slides are copies of them
        self.sample_count = len(prs.slides)
        self.decor = _common_decor(prs, self.samples)
        return prs

    # --- slides on the template's layouts ---

    def layout_for(self, role: str) -> Any:
        assert self.info is not None
        for candidate in (role, *FALLBACK_ROLES):
            index = self.info.roles.get(candidate)
            if index is not None:
                return self.prs.slide_layouts[index]
        return self.prs.slide_layouts[0]

    def has_role(self, role: str) -> bool:
        assert self.info is not None
        return role in self.info.roles

    def new_slide(
        self, layout: str, title: str, notes: str, background: str | None = None, role: str = "title_only"
    ) -> Any:
        slide = self.prs.slides.add_slide(
            self.layout_for(role)
        )  # the template's own background and logo come with it
        if notes:
            slide.notes_slide.notes_text_frame.text = notes
        self.report = SlideReport(len(self.prs.slides) - self.sample_count, layout, title)
        self.reports.append(self.report)
        self._add_decor(slide)
        return slide

    def title(self, slide: Any, text: str, size: float = 34, colour: str | None = None, **frame: Any) -> Any:
        placeholder = slide.shapes.title
        if any(key in frame for key in ("x", "y", "w", "h")):  # a designed slide placing its own title
            return super().title(slide, text, size, colour, **frame)
        if placeholder is None:
            return None
        placeholder.text_frame.text = text  # formatting comes from the template
        if len(text.split()) > 14:
            self.warn(
                f"the title has {len(text.split())} words: keep it short so it fits the template's title area"
            )
        return placeholder

    def add_footer(self, slide: Any) -> None:
        """The template owns its footer; nothing is drawn."""

    def finish(self) -> None:
        sld_ids = self.prs.slides._sldIdLst
        for slide_id in list(sld_ids)[: self.sample_count]:  # the template's sample slides are not ours
            self.prs.part.drop_rel(slide_id.rId)
            sld_ids.remove(slide_id)
        self.sample_count = 0
        for slide in self.prs.slides:  # an empty placeholder shows as "Click to add text" in PowerPoint
            for shape in list(slide.placeholders):
                kind = shape.placeholder_format.type
                if kind is not None and kind.name in TITLE_KINDS:
                    continue
                if shape.has_text_frame and not shape.text_frame.text.strip():
                    shape._element.getparent().remove(shape._element)

    # --- helpers for the placeholders ---

    @staticmethod
    def _holders(slide: Any, kinds: tuple[str, ...]) -> list[Any]:
        return [
            p
            for p in slide.placeholders
            if p.placeholder_format.type is not None and p.placeholder_format.type.name in kinds
        ]

    def _canvas_size(self, shape: Any) -> tuple[float, float]:
        assert self.info is not None
        return shape.width / 914400 / self.info.scale, shape.height / 914400 / self.info.scale

    def _fill_paragraphs(self, frame: Any, items: list[tuple[str, int]], bold_first: bool = False) -> None:
        for index, (text, level) in enumerate(items):
            paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            paragraph.level = min(level, 4)
            run = paragraph.add_run()
            run.text = text
            if bold_first and index == 0:
                run.font.bold = True

    def _warn_bullets(self, items: list[tuple[str, int]], shape: Any) -> None:
        width, height = self._canvas_size(shape)
        _, fits = fit.fit_size(
            [(t, 1.0, False) for t, _ in items], width - 0.3, height, 24, MIN_BODY_PT, gap_pt=10
        )
        if not fits:
            self.warn(
                f"too much text for the template's body area at {MIN_BODY_PT} pt: split it into two slides or cut words"
            )
        top = [t for t, level in items if level == 0]
        if len(top) > MAX_BULLETS:
            self.warn(f"{len(top)} bullets: keep to {MAX_BULLETS} or fewer")
        for text in top:
            if len(text.split()) > MAX_BULLET_WORDS:
                self.warn(
                    f"a bullet has {len(text.split())} words: bullets are short phrases ({text[:40]}...)"
                )
                break

    # --- the template's own sample slides ---

    def _add_decor(self, slide: Any) -> None:
        """A slide made from a layout carries the decoration the template's samples share (once)."""
        present = {_signature(s) for s in slide.shapes if s.left is not None}
        tree = slide.shapes._spTree
        for element in self.decor:
            copy = deepcopy(element)
            ids = [int(i) for i in tree.xpath("//p:cNvPr/@id")] or [1]
            copy.xpath(".//p:cNvPr")[0].set("id", str(max(ids) + 1))
            tree.append(copy)
            if _signature(slide.shapes[len(slide.shapes) - 1]) in present:
                tree.remove(copy)

    def match(self, kind: str) -> Sample | None:
        """The next sample of this kind (round robin, so a deck with several bullet slides does not repeat one sample)."""
        options = [s for s in self.samples if s.kind == kind and not s.charts and not s.tables]
        if not options:
            return None
        count = self.used_samples.get(kind, 0)
        self.used_samples[kind] = count + 1
        return options[count % len(options)]

    def _from_sample(
        self, sample: Sample, label: str, title: str, notes: str, fills: dict[str, Any], strict: bool = False
    ) -> Any:
        try:
            _duplicate(self.prs, sample.number, len(self.prs.slides) + 1)
        except DeckError as error:
            raise BuildError(f"sample slide {sample.number} cannot be copied: {error}") from error
        slide = self.prs.slides[len(self.prs.slides) - 1]
        self.report = SlideReport(len(self.prs.slides) - self.sample_count, label, title)
        self.reports.append(self.report)
        if notes:
            slide.notes_slide.notes_text_frame.text = notes
        picture = fills.pop("picture", None)
        problems = fill_sample(slide, sample, fills)
        if problems and strict:  # content the model gave would silently be lost: make it fix the outline
            raise BuildError(
                f"slide {self.report.number}: the content does not fit sample slide {sample.number} [{sample.kind}]: "
                + "; ".join(problems)
                + ". analyze_template lists each sample's slots"
            )
        for problem in problems:
            self.warn(problem)
        if picture:
            self._replace_picture(slide, str(picture))
        return slide

    def _replace_picture(self, slide: Any, name: str) -> None:
        shape = next((s for s in walk(slide.shapes) if s.shape_type == 13), None)
        if shape is None:
            self.warn("this sample has no picture to replace")
            return
        try:
            data = self.picture_bytes(name)
        except (OSError, ValueError, KeyError) as error:
            raise BuildError(f"the picture {name!r} could not be read: {error}") from error
        _, relation = slide.part.get_or_add_image_part(io.BytesIO(data))
        shape._element.blipFill.blip.rEmbed = relation  # the crop and the frame of the sample stay

    def template_slide(self, slide_spec: TemplateSlide) -> None:
        if not 1 <= slide_spec.source <= len(self.samples):
            have = (
                ", ".join(f"{s.number} [{s.kind}]" for s in self.samples)
                or "none (the template has no sample slides)"
            )
            raise BuildError(f"the template has no sample slide {slide_spec.source}; it has: {have}")
        sample = self.samples[slide_spec.source - 1]
        fills = dict(slide_spec.fill)
        title = str(fills.get("title") or f"sample slide {sample.number}")
        self._from_sample(
            sample, f"template_slide ({sample.kind})", title, slide_spec.notes, fills, strict=True
        )

    def _auto(self, kind: str, label: str, title: str, notes: str, fills: dict[str, Any]) -> bool:
        """Use the template's own sample of this kind when it has one: only the slots the sample has are filled."""
        sample = self.match(kind)
        if sample is None:
            return False
        have = {s.role for s in sample.slots if not s.fixed}
        wanted = {
            k: v for k, v in fills.items() if k in have or k in ("items", "picture") or k.startswith("slot:")
        }
        self._from_sample(sample, f"{label} (template sample {sample.number})", title, notes, wanted)
        return True

    @staticmethod
    def _body_slot(sample: Sample) -> str | None:
        """The slot that holds the bullets: the body, else the text box with the most paragraphs."""
        if sample.slot("body") is not None:
            return "body"
        texts = [s for s in sample.slots if s.role == "text" and not s.fixed and not sample._in_items(s)]
        return f"slot:{max(texts, key=lambda s: s.paragraphs).id}" if texts else None

    # --- the layouts ---

    def title_slide(self, slide_spec: TitleSlide | ClosingSlide, closing: bool) -> None:
        subtitle = slide_spec.subtitle or (self.deck.subtitle if not closing else "")
        lines = [subtitle] if subtitle else []
        if self.deck.author and not closing:
            lines.append(self.deck.author)
        fills: dict[str, Any] = {"title": slide_spec.title, **({"subtitle": lines} if lines else {})}
        kind = "thanks" if closing else "title"
        if self._auto(
            kind, "closing" if closing else "title", slide_spec.title, slide_spec.notes, dict(fills)
        ):
            return
        if closing and self._auto("title", "closing", slide_spec.title, slide_spec.notes, dict(fills)):
            return
        if not self.has_role("title"):
            return super().title_slide(slide_spec, closing)
        slide = self.new_slide(slide_spec.layout, slide_spec.title, slide_spec.notes, role="title")
        slide.shapes.title.text_frame.text = slide_spec.title
        subtitle = slide_spec.subtitle or (self.deck.subtitle if not closing else "")
        lines = [subtitle] if subtitle else []
        if self.deck.author and not closing:
            lines.append(self.deck.author)
        holders = self._holders(slide, ("SUBTITLE",))
        if holders and lines:
            self._fill_paragraphs(holders[0].text_frame, [(line, 0) for line in lines])

    def section_slide(self, slide_spec: SectionSlide) -> None:
        fills: dict[str, Any] = {"title": slide_spec.title}
        if slide_spec.subtitle:
            fills["subtitle"] = slide_spec.subtitle
        if self._auto("section", "section", slide_spec.title, slide_spec.notes, fills):
            return
        if not self.has_role("section"):
            return super().section_slide(slide_spec)
        slide = self.new_slide(slide_spec.layout, slide_spec.title, slide_spec.notes, role="section")
        slide.shapes.title.text_frame.text = slide_spec.title
        holders = self._holders(slide, BODY_KINDS)
        if holders and slide_spec.subtitle:
            holders[0].text_frame.text = slide_spec.subtitle

    def bullets_slide(self, slide_spec: BulletsSlide) -> None:
        sample = self.match("bullets")
        if sample is not None and (target := self._body_slot(sample)) is not None:
            lines = ["  " * level + text for text, level in self.bullet_items(slide_spec.bullets)]
            label = f"bullets (template sample {sample.number})"
            self._from_sample(
                sample, label, slide_spec.title, slide_spec.notes, {"title": slide_spec.title, target: lines}
            )
            return
        if not self.has_role("content"):
            return super().bullets_slide(slide_spec)
        slide = self.new_slide(slide_spec.layout, slide_spec.title, slide_spec.notes, role="content")
        self.title(slide, slide_spec.title)
        holders = self._holders(slide, BODY_KINDS)
        if not holders:
            return super().bullets_slide(slide_spec)
        items = self.bullet_items(slide_spec.bullets)
        self._warn_bullets(items, holders[0])
        self._fill_paragraphs(holders[0].text_frame, items)

    def two_column_slide(self, slide_spec: TwoColumnSlide) -> None:
        sample = self.match("two_column")
        if sample is not None and len(sample.items) == 2:
            columns = [
                {"heading": c.heading, "text": [text for text, _ in self.bullet_items(c.bullets)]}
                for c in (slide_spec.left, slide_spec.right)
            ]
            label = f"two_column (template sample {sample.number})"
            self._from_sample(
                sample,
                label,
                slide_spec.title,
                slide_spec.notes,
                {"title": slide_spec.title, "items": columns},
            )
            return
        if not self.has_role("two_content"):
            return super().two_column_slide(slide_spec)
        slide = self.new_slide(slide_spec.layout, slide_spec.title, slide_spec.notes, role="two_content")
        self.title(slide, slide_spec.title)
        holders = sorted(self._holders(slide, BODY_KINDS), key=lambda p: p.left)
        for holder, column in zip(holders, (slide_spec.left, slide_spec.right), strict=False):
            items = self.bullet_items(column.bullets)
            self._warn_bullets(items, holder)
            if column.heading:
                items = [(column.heading, 0), *items]
            self._fill_paragraphs(holder.text_frame, items, bold_first=bool(column.heading))

    def stats_slide(self, slide_spec: StatsSlide) -> None:
        sample = next(
            (s for s in self.samples if s.kind == "stats" and len(s.items) >= len(slide_spec.items)), None
        )
        if sample is not None:
            has_heading = "heading" in sample.items[0].parts
            items = [
                {"number": s.value, ("heading" if has_heading else "text"): s.label} for s in slide_spec.items
            ]
            label = f"stats (template sample {sample.number})"
            self._from_sample(
                sample, label, slide_spec.title, slide_spec.notes, {"title": slide_spec.title, "items": items}
            )
            return
        super().stats_slide(slide_spec)

    def _items_from_sample(
        self, kind: str, label: str, title: str, notes: str, entries: list[dict[str, str]]
    ) -> bool:
        """Cards and steps use the template's own sample of that kind when it has room for all the items."""
        sample = next(
            (s for s in self.samples if s.kind == kind and len(s.items) >= len(entries) and not s.charts),
            None,
        )
        if sample is None:
            return False
        parts = sample.items[0].parts
        items = [{k: v for k, v in entry.items() if k in parts and v} for entry in entries]
        self._from_sample(
            sample,
            f"{label} (template sample {sample.number})",
            title,
            notes,
            {"title": title, "items": items},
        )
        return True

    def cards_slide(self, slide_spec: CardsSlide) -> None:
        entries = [
            {"heading": c.heading, "text": c.text, **({"number": c.number} if c.number else {})}
            for c in slide_spec.items
        ]
        if not self._items_from_sample("cards", "cards", slide_spec.title, slide_spec.notes, entries):
            super().cards_slide(slide_spec)

    def steps_slide(self, slide_spec: StepsSlide) -> None:
        entries = [
            {"heading": s.heading, "text": s.text, "number": str(i)}
            for i, s in enumerate(slide_spec.steps, start=1)
        ]
        if not self._items_from_sample("steps", "steps", slide_spec.title, slide_spec.notes, entries):
            super().steps_slide(slide_spec)

    def column(self, slide: Any, column: Column, x: float, width: float) -> None:
        super().column(slide, column, x, width)

    def quote_slide(self, slide_spec: QuoteSlide) -> None:
        slide = self.new_slide(slide_spec.layout, slide_spec.quote[:60], slide_spec.notes, role="blank")
        if slide.shapes.title is not None:
            slide.shapes.title.text_frame.text = slide_spec.quote[:60]  # navigation title for screen readers
        x, y, w, h = self.margin, self.body_top, self.content_width, self.body_bottom - self.body_top
        frame = self.textbox(slide, x, y, w, h * 0.7, anchor="middle")
        size, fits = fit.fit_size([(f"“{slide_spec.quote}”", 1.0, True)], w, h * 0.7, 36, 22)
        if not fits:
            self.warn("the quote is too long for one slide: shorten it")
        self.paragraph(frame, True, f"“{slide_spec.quote}”", size, self.theme.text, bold=True, heading=True)
        if slide_spec.by:
            note = self.textbox(slide, x, y + h * 0.75, w, 0.5)
            self.paragraph(note, True, f"— {slide_spec.by}", 20, self.theme.muted)
