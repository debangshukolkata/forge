"""Edit operations for slide features (TODO P2.8, D-316): hide, transition, animation, sections, comments. The XML is in features.py."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from forge.slides import features
from forge.slides.edit_base import Op as _Op
from forge.slides.edit_find import find_shape, slide_at


class HideSlide(_Op):
    op: Literal["hide_slide"]
    slide: int
    hidden: bool = True  # false shows it again


class SetTransition(_Op):
    op: Literal["set_transition"]
    slide: int | None = None  # default every slide
    kind: Literal["fade", "push", "wipe", "split", "cover", "none"] = "fade"
    speed: Literal["slow", "medium", "fast"] = "medium"
    advance_after: float | None = Field(
        default=None, gt=0, le=3600
    )  # seconds; the slide also advances by itself


class AnimateShape(_Op):
    op: Literal["animate"]
    slide: int
    shape: int | str  # id, name or "text:..." as in set_text
    effect: Literal["appear", "fade", "wipe"] = "fade"
    start: Literal["on_click", "with_previous", "after_previous"] = "on_click"


class ClearAnimations(_Op):
    op: Literal["clear_animations"]
    slide: int | None = None  # default every slide


class SectionStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    from_slide: int = Field(ge=1)


class SetSections(_Op):
    op: Literal["set_sections"]
    sections: list[SectionStart]  # empty removes all sections; the first starts at slide 1


class AddComment(_Op):
    op: Literal["add_comment"]
    slide: int
    text: str = Field(min_length=1, max_length=2000)
    author: str = "DebCraft"


FeatureOperation = HideSlide | SetTransition | AnimateShape | ClearAnimations | SetSections | AddComment
FEATURE_OPERATIONS = "hide_slide, set_transition, animate, clear_animations, set_sections, add_comment"
FEATURE_TYPES = (HideSlide, SetTransition, AnimateShape, ClearAnimations, SetSections, AddComment)


def apply_feature(deck: Any, operation: Any) -> str:
    if isinstance(operation, HideSlide):
        features.set_hidden(slide_at(deck, operation.slide), operation.hidden)
        return f"{'hid' if operation.hidden else 'showed'} slide {operation.slide}"
    if isinstance(operation, SetTransition):
        slides = [slide_at(deck, operation.slide)] if operation.slide else list(deck.slides)
        for slide in slides:
            features.set_transition(slide, operation.kind, operation.speed, operation.advance_after)
        return f"set the transition '{operation.kind}' on {len(slides)} slide(s)"
    if isinstance(operation, AnimateShape):
        slide = slide_at(deck, operation.slide)
        shape = find_shape(slide, operation.shape)
        features.add_animation(slide, shape, operation.effect, operation.start)
        return f'"{shape.name}" on slide {operation.slide} now appears with {operation.effect} ({operation.start})'
    if isinstance(operation, ClearAnimations):
        slides = [slide_at(deck, operation.slide)] if operation.slide else list(deck.slides)
        return f"removed {sum(features.clear_animations(slide) for slide in slides)} animation(s)"
    if isinstance(operation, SetSections):
        features.set_sections(deck, [features.Section(s.name, s.from_slide) for s in operation.sections])
        return f"set {len(operation.sections)} section(s)"
    features.add_comment(deck, operation.slide, operation.text, operation.author)
    return f"added a comment to slide {operation.slide}"
