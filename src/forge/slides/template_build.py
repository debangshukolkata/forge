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
from typing import Any

from forge.slides import fit
from forge.slides.build import (
    MAX_BULLET_WORDS,
    MAX_BULLETS,
    MIN_BODY_PT,
    SlideReport,
    _Builder,
)
from forge.slides.errors import BuildError
from forge.slides.spec import (
    BulletsSlide,
    ClosingSlide,
    Column,
    Deck,
    QuoteSlide,
    SectionSlide,
    TitleSlide,
    TwoColumnSlide,
)
from forge.slides.template import TemplateInfo, analyze_template, content_box, theme_from_template
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


class TemplateBuilder(_Builder):
    def __init__(self, deck: Deck, read_image: Any, template: bytes) -> None:
        self.template_bytes = template
        self.info: TemplateInfo | None = None
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
        sld_ids = prs.slides._sldIdLst
        for slide_id in list(sld_ids):  # the template's sample slides are not ours
            prs.part.drop_rel(slide_id.rId)
            sld_ids.remove(slide_id)
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
        self.report = SlideReport(len(self.prs.slides), layout, title)
        self.reports.append(self.report)
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

    # --- the layouts ---

    def title_slide(self, slide_spec: TitleSlide | ClosingSlide, closing: bool) -> None:
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
        if not self.has_role("section"):
            return super().section_slide(slide_spec)
        slide = self.new_slide(slide_spec.layout, slide_spec.title, slide_spec.notes, role="section")
        slide.shapes.title.text_frame.text = slide_spec.title
        holders = self._holders(slide, BODY_KINDS)
        if holders and slide_spec.subtitle:
            holders[0].text_frame.text = slide_spec.subtitle

    def bullets_slide(self, slide_spec: BulletsSlide) -> None:
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
