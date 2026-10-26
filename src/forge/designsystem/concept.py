"""The concept step of a brand page's DESIGN.md (D-486).

Seven design skills given one brief all produced the same kind of page: a headline, a card, three columns of text, no picture that belonged to the
product. The skill text already asked for "a hero picture that belongs to the product", but nothing made the model decide what it is before it wrote
markup. A brand page's DESIGN.md now opens with a `## Concept` section: the idea in one sentence and the signature visual that carries the hero
(what it shows, how it is made, how large). Application screens are exempt. Only the model's own DESIGN.md and its candidates are checked; a file
the user supplied is never questioned."""

from __future__ import annotations

import re

SECTION = re.compile(r"^##[ \t]+Concept[ \t]*$", re.IGNORECASE | re.MULTILINE)
NEXT_SECTION = re.compile(r"^##[ \t]", re.MULTILINE)
LABEL = re.compile(r"^[\W_]*(idea|signature visual|why not generic)[\W_]*:", re.IGNORECASE | re.MULTILINE)
APPLICATION = re.compile(r"^composition:\s*app-", re.IGNORECASE | re.MULTILINE)
MADE_FROM = re.compile(
    r"\b(drawn|svg|illustration|illustrated|photo|photograph|find_image|generate_image|brand folder|product shot|screenshot|video|canvas|3d|render)\b",
    re.IGNORECASE,
)
MIN_CHARS = 30

HOW_TO_FIX = (
    "Add `## Concept` as the first section after the front matter, with two lines: `Idea:` one sentence on what this page is about, taken from the subject's own world "
    "(not a style word such as 'clean' or 'modern'), and `Signature visual:` the one picture that carries the hero: what it shows, how it is made (a drawn SVG scene, a licensed "
    "photograph found with find_image, a product shot) and how large it is on the page. Optional third line `Why not generic:` what the obvious version would be. "
    "ONE edit, not a rewrite."
)


def concept_fields(text: str) -> dict[str, str]:
    """The labelled lines of the Concept section, lower-cased label to its text; empty when there is no such section."""
    start = SECTION.search(text)
    if start is None:
        return {}
    rest = text[start.end() :]
    following = NEXT_SECTION.search(rest)
    body = rest[: following.start()] if following else rest
    marks = list(LABEL.finditer(body))
    fields: dict[str, str] = {}
    for index, mark in enumerate(marks):
        end = marks[index + 1].start() if index + 1 < len(marks) else len(body)
        fields[mark.group(1).lower()] = " ".join(body[mark.end() : end].split())
    return fields


def concept_problem(text: str) -> str:
    """What is wrong with the Concept of a brand page's DESIGN.md, or an empty string when it is fine (or the file describes an application screen)."""
    if APPLICATION.search(text):
        return ""
    fields = concept_fields(text)
    idea = fields.get("idea", "")
    visual = fields.get("signature visual", "")
    if not idea or not visual:
        return "No Concept yet (the `Idea:` and `Signature visual:` lines). " + HOW_TO_FIX
    if len(idea) < MIN_CHARS or "<" in idea or "..." in idea:
        return (
            "The Concept's `Idea:` is empty or a placeholder: say in one real sentence what this page is about. "
            + HOW_TO_FIX
        )
    if len(visual) < MIN_CHARS or "<" in visual or "..." in visual:
        return (
            "The Concept's `Signature visual:` is empty or a placeholder: say what the hero picture shows. "
            + HOW_TO_FIX
        )
    if not MADE_FROM.search(visual):
        return (
            "The Concept's `Signature visual:` does not say how the picture is made (a drawn SVG scene, a photograph from find_image, a product shot). "
            + HOW_TO_FIX
        )
    return ""


def same_idea(first: str, second: str) -> bool:
    """Two candidates with the same Idea are one design in two colours."""
    one = " ".join(concept_fields(first).get("idea", "").lower().split())
    two = " ".join(concept_fields(second).get("idea", "").lower().split())
    return bool(one) and one == two
