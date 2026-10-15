"""The design blueprint checks of a DESIGN.md (TODO DIE2): are the decisions beyond the tokens written down, and does each say why?

The tokens say what; a blueprint also says how the page is composed, where its pictures come from, how it moves, how it adapts and what keeps it usable
for everyone, with a reason for each choice. These findings are notes (`info`), never errors: older files and the shipped examples stay valid, and the
design critic and the user read the notes as questions."""

from __future__ import annotations

import re

from forge.designsystem.spec import DesignSystem, Section

# blueprint part -> (label, headings that answer it, hint for the author)
BLUEPRINT_PARTS: dict[str, tuple[str, tuple[str, ...], str]] = {
    "experience": (
        "Experience",
        ("experience",),
        "who it is for, the feeling in a few words and what it must not feel like, the reaction wanted, or for an application the people, tasks and outcomes (written before any token, D-434)",
    ),
    "story": (
        "Story",
        ("story", "page story", "journey"),
        "the journey of a visitor as an ordered list: each section's job, its density (quiet, rich or dramatic) and the picture it needs",
    ),
    "composition": (
        "Page Composition",
        ("page composition", "section composition"),
        "the order of the sections on each page, what each one is for and which layout recipe it comes from",
    ),
    "imagery": (
        "Imagery and Icons",
        ("imagery and icons",),
        "where every picture comes from (the brand folder, an open set, a photograph, a drawn SVG) and the style rules",
    ),
    "motion": (
        "Motion and Interaction",
        ("motion and interaction", "motion"),
        "what moves, how long it takes, the hover, focus and loading states, and what stays still",
    ),
    "responsive": (
        "Responsive Behavior",
        ("responsive behavior", "responsive behaviour"),
        "what collapses at 375, 768 and 1280 px",
    ),
    "accessibility": (
        "Accessibility",
        ("accessibility",),
        "contrast, focus order, touch targets, reduced motion and the reading order",
    ),
}
# A decision states its purpose with one of these (a reason word, or a dash that introduces it).
PURPOSE = re.compile(
    r"\b(because|so that|so the|so it|so they|so a|in order|since|why|reason|to keep|to make|to let|to avoid|to show|to signal|to help|means)\b"
    r"|\s[-\u2013\u2014]\s|:\s*\w",
    re.I,
)
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.+)$")


def _bullets(section: Section) -> list[str]:
    return [m.group(1) for line in section.body.splitlines() if (m := BULLET.match(line))]


def _section_for(system: DesignSystem, headings: tuple[str, ...]) -> Section | None:
    for section in system.sections:
        if section.heading.strip().lower() in headings:
            return section
    return None


DENSITY_WORDS = ("quiet", "rich", "dramatic")


def _is_application(system: DesignSystem) -> bool:
    return str(system.extra.get("composition", "")).strip().lower().startswith("app-")


def check_blueprint(system: DesignSystem) -> list[tuple[str, str, str, str]]:
    """(severity, rule, path, message) for each missing blueprint part and each part whose decisions lack a stated purpose."""
    findings: list[tuple[str, str, str, str]] = []
    omitted = {item.lower() for item in system.omitted}
    for key, (label, headings, hint) in BLUEPRINT_PARTS.items():
        if key == "story" and _is_application(system):
            continue  # an application's journey is its tasks, written under Experience
        section = _section_for(system, headings)
        if section is None:
            if key in omitted or label.lower() in omitted:
                continue
            findings.append(
                (
                    "info",
                    "blueprint-missing",
                    label,
                    f"no {label} section: write {hint} (or list {key} under omitted with a reason)",
                )
            )
            continue
        bullets = _bullets(section)
        if key == "story":
            densities = {word for word in DENSITY_WORDS if word in section.body.lower()}
            if len(bullets) < 3 or len(densities) < 2:
                findings.append(
                    (
                        "info",
                        "story-without-rhythm",
                        section.heading,
                        f"the story has {len(bullets)} step(s) and names {len(densities)} density level(s): write at least three sections and let neighbours differ (quiet, rich, dramatic)",
                    )
                )
            continue
        without = [b for b in bullets if not PURPOSE.search(b)]
        if len(bullets) >= 2 and len(without) * 2 > len(bullets):
            findings.append(
                (
                    "info",
                    "decision-without-purpose",
                    section.heading,
                    f"{len(without)} of {len(bullets)} decisions give no reason (for example: {without[0][:70]!r}): say why each is right for this product",
                )
            )
    return findings
