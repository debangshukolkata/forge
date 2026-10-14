"""Lint a DESIGN.md (D-348): structure, references, units, contrast, and a few look problems.

Severity: `error` makes the file unusable as a source of truth (the design gate and exports refuse it), `warning` is something to fix, `info` is a
note. Rule names are stable so a finding can be quoted and ignored by name."""

from __future__ import annotations

import re
from dataclasses import dataclass

from forge.designsystem.colour import contrast, hue_and_saturation, parse
from forge.designsystem.spec import (
    KNOWN_EXTRAS,
    REFERENCE,
    SECTION_ORDER,
    TOKEN_GROUPS,
    DesignMdError,
    DesignSystem,
    parse_design_md,
)

DIMENSION = re.compile(r"^-?\d+(?:\.\d+)?(px|em|rem)$")
COMPONENT_PROPERTIES = {
    "backgroundColor",
    "textColor",
    "typography",
    "rounded",
    "padding",
    "size",
    "height",
    "width",
}
TYPOGRAPHY_PROPERTIES = {
    "fontFamily",
    "fontSize",
    "fontWeight",
    "lineHeight",
    "letterSpacing",
    "fontFeature",
    "fontVariation",
}
CONTRAST_MINIMUM = 4.5
MAX_ACCENT_HUES = 3
ONE_HUE_SPREAD = 25  # degrees: every coloured token inside this arc is a one-note palette


@dataclass(frozen=True)
class Finding:
    severity: str  # "error", "warning" or "info"
    rule: str
    path: str  # where in the file, e.g. colors.primary or components.button-primary.textColor
    message: str


def _check_references(system: DesignSystem, findings: list[Finding]) -> None:
    def walk(path: str, value: object) -> None:
        if isinstance(value, dict):
            for key, inner in value.items():
                walk(f"{path}.{key}", inner)
        elif isinstance(value, str) and value.strip().startswith("{") and value.strip().endswith("}"):
            match = REFERENCE.match(value.strip())
            if not match:
                findings.append(
                    Finding(
                        "error",
                        "bad-reference",
                        path,
                        f"{value!r} is not a valid reference: write {{colors.primary}}",
                    )
                )
                return
            target = system.lookup(match.group(1))
            if target is None:
                findings.append(
                    Finding(
                        "error", "broken-reference", path, f"{value} points to a token that does not exist"
                    )
                )
            elif (
                isinstance(target, dict)
                and not path.startswith("components.")
                and match.group(1).split(".")[0] != "typography"
            ):
                findings.append(
                    Finding("error", "reference-to-group", path, f"{value} names a group, not a single value")
                )

    for group in TOKEN_GROUPS:
        walk(group, system.group(group))


def _check_values(system: DesignSystem, findings: list[Finding]) -> None:
    for name, value in system.colors.items():
        resolved = system.resolve(value)
        if not isinstance(resolved, str) or parse(resolved) is None:
            findings.append(
                Finding(
                    "error"
                    if not str(resolved).startswith(("oklch", "oklab", "color(", "color-mix", "var("))
                    else "info",
                    "bad-colour",
                    f"colors.{name}",
                    f"{value!r} is not a colour this tool understands (hex, rgb(), hsl() or a name)",
                )
            )
    for group in ("rounded", "spacing"):
        for name, value in system.group(group).items():
            resolved = system.resolve(value)
            if isinstance(resolved, (int, float)) and group == "spacing":
                continue
            if not (
                isinstance(resolved, str)
                and (DIMENSION.match(resolved) or resolved in ("0", "9999px", "50%", "full"))
            ):
                findings.append(
                    Finding(
                        "error",
                        "bad-dimension",
                        f"{group}.{name}",
                        f"{value!r} must be a number with px, em or rem, e.g. 8px",
                    )
                )
    for name, style in system.typography.items():
        if not isinstance(style, dict):
            findings.append(
                Finding(
                    "error",
                    "bad-typography",
                    f"typography.{name}",
                    "a typography token is a mapping with fontFamily, fontSize, ...",
                )
            )
            continue
        for key in style:
            if key not in TYPOGRAPHY_PROPERTIES:
                findings.append(
                    Finding(
                        "warning",
                        "unknown-typography-property",
                        f"typography.{name}.{key}",
                        f"{key} is not a typography property of the format",
                    )
                )
        for needed in ("fontFamily", "fontSize"):
            if needed not in style:
                findings.append(
                    Finding("warning", "typography-incomplete", f"typography.{name}", f"no {needed}")
                )
        size = system.resolve(style.get("fontSize"))
        if size is not None and not (isinstance(size, str) and DIMENSION.match(size)):
            findings.append(
                Finding(
                    "error",
                    "bad-dimension",
                    f"typography.{name}.fontSize",
                    f"{size!r} must be a number with px, em or rem",
                )
            )
        weight = style.get("fontWeight")
        if weight is not None and not (isinstance(weight, int) and 100 <= weight <= 1000):
            findings.append(
                Finding(
                    "warning",
                    "bad-font-weight",
                    f"typography.{name}.fontWeight",
                    f"{weight!r} should be a number such as 400 or 700",
                )
            )
    for name, component in system.components.items():
        if not isinstance(component, dict):
            findings.append(
                Finding(
                    "error", "bad-component", f"components.{name}", "a component is a mapping of properties"
                )
            )
            continue
        for key in component:
            if key not in COMPONENT_PROPERTIES:
                findings.append(
                    Finding(
                        "warning",
                        "unknown-component-property",
                        f"components.{name}.{key}",
                        f"{key} is not a component property of the format",
                    )
                )
        for key in ("backgroundColor", "textColor"):
            value = system.resolve(component.get(key))
            if value is not None and not (isinstance(value, str) and parse(value) is not None):
                findings.append(
                    Finding(
                        "error",
                        "bad-colour",
                        f"components.{name}.{key}",
                        f"{component.get(key)!r} does not resolve to a colour",
                    )
                )


def _check_contrast(system: DesignSystem, findings: list[Finding]) -> None:
    for name, component in system.components.items():
        if not isinstance(component, dict):
            continue
        background, text = (
            system.resolve(component.get("backgroundColor")),
            system.resolve(component.get("textColor")),
        )
        if isinstance(background, str) and isinstance(text, str):
            ratio = contrast(background, text)
            if ratio is not None and ratio < CONTRAST_MINIMUM:
                findings.append(
                    Finding(
                        "error",
                        "low-contrast",
                        f"components.{name}",
                        f"text {text} on {background} is {ratio:.1f}:1; body text needs {CONTRAST_MINIMUM}:1",
                    )
                )
    canvas = next(
        (
            system.resolve(system.colors[k])
            for k in ("canvas", "background", "surface", "neutral", "bg")
            if k in system.colors
        ),
        None,
    )
    ink = next(
        (
            system.resolve(system.colors[k])
            for k in ("ink", "text", "foreground", "on-surface", "primary")
            if k in system.colors
        ),
        None,
    )
    if isinstance(canvas, str) and isinstance(ink, str):
        ratio = contrast(canvas, ink)
        if ratio is not None and ratio < CONTRAST_MINIMUM:
            findings.append(
                Finding(
                    "error",
                    "low-contrast",
                    "colors",
                    f"the main text colour {ink} on the page colour {canvas} is {ratio:.1f}:1; it needs {CONTRAST_MINIMUM}:1",
                )
            )


def _check_palette(system: DesignSystem, findings: list[Finding]) -> None:
    hues: list[float] = []
    for value in system.colors.values():
        resolved = system.resolve(value)
        measured = hue_and_saturation(resolved) if isinstance(resolved, str) else None
        if measured and measured[1] > 0.25 and 0.12 < measured[2] < 0.9:
            hues.append(measured[0])
    if len(hues) >= 4:
        spread = max(min((a - b) % 360, (b - a) % 360) for a in hues for b in hues)
        if spread <= ONE_HUE_SPREAD:
            findings.append(
                Finding(
                    "warning",
                    "one-note-palette",
                    "colors",
                    "every coloured token sits in one hue family: add a deliberate contrast colour or say why not",
                )
            )
    buckets = {round(h / 40) % 9 for h in hues}
    if len(buckets) > MAX_ACCENT_HUES + 2:
        findings.append(
            Finding(
                "warning",
                "too-many-accents",
                "colors",
                f"{len(buckets)} different hue families: keep one accent and one signal colour",
            )
        )


def _check_structure(system: DesignSystem, findings: list[Finding]) -> None:
    omitted = {o.lower() for o in system.omitted}
    if not system.name:
        findings.append(Finding("error", "missing-name", "name", "the front matter needs a name"))
    for group in system.invalid_groups:
        findings.append(Finding("error", "bad-group", group, f"{group} must be a mapping of tokens"))
    if "primary" not in system.colors and system.colors:
        findings.append(
            Finding(
                "error", "missing-primary", "colors.primary", "at least the primary colour must be defined"
            )
        )
    for group in TOKEN_GROUPS:
        if not system.group(group) and group not in omitted and group not in system.invalid_groups:
            findings.append(
                Finding(
                    "warning",
                    "missing-section",
                    group,
                    f"no {group} tokens (add them, or list {group} under omitted with a reason)",
                )
            )
    seen: set[str] = set()
    last_rank = -1
    for section in system.sections:
        key = section.heading.lower()
        if key in seen:
            findings.append(
                Finding(
                    "error",
                    "duplicate-section",
                    section.heading,
                    "the same heading appears twice: the file is rejected by the format",
                )
            )
        seen.add(key)
        if section.canonical:
            rank = SECTION_ORDER.index(section.canonical)
            if rank < last_rank:
                findings.append(
                    Finding(
                        "warning",
                        "section-order",
                        section.heading,
                        "sections follow the order Overview, Colors, Typography, Layout, Elevation, Shapes, Components, Do's and Don'ts",
                    )
                )
            last_rank = max(last_rank, rank)
        elif key not in KNOWN_EXTRAS:
            findings.append(
                Finding(
                    "info", "extra-section", section.heading, "a heading the format does not define: kept"
                )
            )
    present = {s.canonical for s in system.sections if s.canonical}
    for needed, label in (("overview", "Overview"), ("dos-and-donts", "Do's and Don'ts")):
        if needed not in present:
            findings.append(
                Finding(
                    "warning",
                    "missing-prose",
                    label,
                    f"no {label} section: the reasoning behind the tokens is what makes the file useful",
                )
            )
    if system.version and system.version != "alpha":
        findings.append(
            Finding(
                "info", "version", "version", f"version {system.version!r}: this tool reads the alpha format"
            )
        )


def lint_system(system: DesignSystem) -> list[Finding]:
    findings: list[Finding] = []
    if not system.has_front_matter:
        findings.append(
            Finding(
                "error",
                "no-front-matter",
                "file",
                "the file must start with a --- YAML block holding name and the tokens; see the recipe design-md-template.md",
            )
        )
        return findings
    _check_structure(system, findings)
    _check_references(system, findings)
    _check_values(system, findings)
    _check_contrast(system, findings)
    _check_palette(system, findings)
    return findings


def lint_text(text: str) -> list[Finding]:
    try:
        return lint_system(parse_design_md(text))
    except DesignMdError as error:
        return [Finding("error", "bad-front-matter", "file", str(error))]


def describe_findings(findings: list[Finding], limit: int = 40) -> str:
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]
    infos = [f for f in findings if f.severity == "info"]
    if not findings:
        return "DESIGN.md is valid: no findings."
    lines = [f"{len(errors)} error(s), {len(warnings)} warning(s), {len(infos)} note(s):"]
    for finding in (errors + warnings + infos)[:limit]:
        lines.append(f"  {finding.severity.upper():7} [{finding.rule}] {finding.path}: {finding.message}")
    return "\n".join(lines)
