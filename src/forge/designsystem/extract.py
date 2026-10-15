"""A DESIGN.md draft from what already exists: a project's own CSS tokens, or the computed styles of a page (D-349).

Only values (colours, font names, sizes, radii) are read. They are a starting point: the draft says so in its Known Gaps, and the model rewrites
the prose and the choices that matter. Nothing here fetches anything."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from forge.brand.kit import readable_on
from forge.designsystem.colour import contrast, hue_and_saturation, parse, to_hex
from forge.designsystem.spec import DesignMdError

CUSTOM_PROPERTY = re.compile(r"--([\w-]+)\s*:\s*([^;{}]+);")
SYSTEM_FONTS = {
    "inherit",
    "initial",
    "unset",
    "system-ui",
    "-apple-system",
    "blinkmacsystemfont",
    "segoe ui",
    "ui-sans-serif",
    "ui-serif",
    "ui-monospace",
}
GENERIC_FAMILIES = {"serif", "sans-serif", "monospace", "cursive", "fantasy"}
SPACING_SCALE = {"xs": "4px", "sm": "8px", "md": "16px", "lg": "32px", "xl": "64px"}


@dataclass
class Extracted:
    colors: dict[str, str] = field(
        default_factory=dict
    )  # role -> hex, e.g. primary, neutral, ink, muted, surface, border
    fonts: list[str] = field(default_factory=list)  # most used first
    heading_font: str = ""
    sizes: list[float] = field(default_factory=list)  # px, ascending
    radii: list[float] = field(default_factory=list)  # px, ascending
    max_width: float = 0.0
    gradients: int = 0
    notes: list[str] = field(default_factory=list)


def _hex(value: str) -> str | None:
    parsed = parse(value)
    if parsed is None or parsed[3] < 0.95:
        return None
    return "#" + to_hex(parsed)


def _saturation(colour: str) -> float:
    measured = hue_and_saturation(colour)
    return measured[1] if measured else 0.0


def _families(text: str) -> list[str]:
    names = [p.strip().strip("\"'") for p in text.split(",")]
    return [
        n
        for n in names
        if n
        and n.lower() not in SYSTEM_FONTS
        and n.lower() not in GENERIC_FAMILIES
        and not n.startswith("var(")
    ]


def _px(text: str) -> float | None:
    match = re.match(r"^(-?\d+(?:\.\d+)?)(px|rem|em)?$", text.strip())
    if not match:
        return None
    value = float(match.group(1))
    return value * 16 if match.group(2) in ("rem", "em") else value


def from_css(css: str) -> Extracted:
    """Tokens from CSS custom properties (`:root` and Tailwind v4 `@theme` blocks)."""
    found = Extracted()
    named: dict[str, str] = {}
    for name, raw in CUSTOM_PROPERTY.findall(css):
        value = raw.strip()
        lowered = name.lower().removeprefix("color-")
        if "font" in lowered or lowered.startswith(("display", "heading", "body")):
            families = _families(value)
            if families:
                found.fonts.extend(f for f in families[:1] if f not in found.fonts)
                if any(k in lowered for k in ("display", "heading", "title")) and not found.heading_font:
                    found.heading_font = families[0]
            continue
        if "radius" in lowered or lowered.startswith("rounded"):
            pixels = _px(value)
            if pixels is not None:
                found.radii.append(pixels)
            continue
        colour = _hex(value)
        if colour is not None:
            named[lowered] = colour
    roles = {
        "primary": ("primary", "accent", "brand", "main"),
        "neutral": ("background", "bg", "canvas", "page", "neutral", "base"),
        "ink": ("foreground", "ink", "text", "fg"),
        "muted": ("muted", "secondary-text", "subtle", "text-muted"),
        "surface": ("surface", "card", "panel", "elevated"),
        "border": ("border", "line", "divider", "hairline"),
    }
    for role, keys in roles.items():
        for key in keys:
            match = next(
                (v for n, v in named.items() if n == key or n.startswith(key + "-") or n.endswith("-" + key)),
                None,
            )
            if match:
                found.colors[role] = match
                break
    for name, colour in named.items():
        if (
            colour not in found.colors.values()
            and len(found.colors) < 10
            and name.split("-")[0]
            in ("secondary", "success", "warning", "error", "danger", "info", "ok", "warn")
        ):
            found.colors[
                name.replace("danger", "error").replace("success", "ok").replace("warning", "warn")
            ] = colour
    found.radii = sorted(set(found.radii))
    return found


def from_computed(data: dict[str, Any]) -> Extracted:
    """Tokens from `computed styles` gathered in a page by the capture script (weighted lists of colours, fonts, sizes, radii)."""
    found = Extracted()
    backgrounds = [(h, w) for h, w in ((_hex(str(c)), w) for c, w in data.get("backgrounds", [])) if h]
    texts = [(h, w) for h, w in ((_hex(str(c)), w) for c, w in data.get("texts", [])) if h]
    accents = [(h, w) for h, w in ((_hex(str(c)), w) for c, w in data.get("accents", [])) if h]
    if backgrounds:
        found.colors["neutral"] = backgrounds[0][0]
    if texts:
        ink = next(
            (c for c, _ in texts if (contrast(c, found.colors.get("neutral", "#FFFFFF")) or 0) >= 4.5),
            texts[0][0],
        )
        found.colors["ink"] = ink
        muted = next(
            (
                c
                for c, _ in texts[1:]
                if c != ink and (contrast(c, found.colors.get("neutral", "#FFFFFF")) or 0) >= 4.5
            ),
            None,
        )
        if muted:
            found.colors["muted"] = muted
    candidates = [c for c, _ in accents + backgrounds + texts if _saturation(c) > 0.3]
    if candidates:
        found.colors["primary"] = candidates[0]
    for colour, _ in backgrounds[1:]:
        if (
            colour != found.colors.get("neutral")
            and "surface" not in found.colors
            and _saturation(colour) < 0.25
        ):
            found.colors["surface"] = colour
    found.fonts = [f for family in data.get("fonts", []) for f in _families(str(family))[:1]]
    found.fonts = list(dict.fromkeys(found.fonts))
    heading = _families(str(data.get("headingFont", "")))
    found.heading_font = heading[0] if heading else ""
    found.sizes = sorted({round(float(s)) for s in data.get("sizes", []) if 8 <= float(s) <= 120})
    found.radii = sorted({round(float(r)) for r in data.get("radii", []) if 0 < float(r) < 200})
    found.max_width = float(data.get("maxWidth", 0) or 0)
    found.gradients = int(data.get("gradients", 0) or 0)
    return found


def draft_design_md(found: Extracted, name: str, source: str) -> str:
    """A DESIGN.md that passes the linter (contrast corrected), with the gaps stated honestly."""
    colors = dict(found.colors)
    gaps = list(found.notes)
    neutral = colors.setdefault("neutral", "#FFFFFF")
    if "ink" not in colors or (contrast(colors["ink"], neutral) or 21) < 4.5:
        if "ink" in colors:
            gaps.append(
                f"the text colour {colors['ink']} was too faint on {neutral} (under 4.5:1) and was replaced"
            )
        colors["ink"] = "#" + readable_on(neutral.lstrip("#"))
    if "primary" not in colors:
        colors["primary"] = colors["ink"]
        gaps.append("no accent colour was found: primary is the text colour; choose a real accent")
    on_primary = "#" + readable_on(colors["primary"].lstrip("#"))
    families = found.fonts or []
    body_font = families[0] if families else "Inter"
    heading_font = found.heading_font or (families[1] if len(families) > 1 else body_font)
    if not families:
        gaps.append("no font family was found: Inter is a placeholder; choose the fonts")
    sizes = found.sizes or [14, 16, 20, 32, 48]
    display = max(sizes[-1], 32) if sizes else 48
    radii = found.radii or [6, 12]
    rounded = {"sm": f"{int(radii[0])}px", "md": f"{int(radii[len(radii) // 2])}px", "pill": "9999px"}
    lines = [
        "---",
        "version: alpha",
        f"name: {_quote(name)}",
        f"description: {_quote('Draft extracted from ' + source + '. Review every value and rewrite the prose.')}",
        "colors:",
    ]
    lines += [f'  {role}: "{value.upper()}"' for role, value in colors.items()]
    lines += [
        "typography:",
        "  display:",
        f"    fontFamily: {_quote(heading_font)}",
        f"    fontSize: {display}px",
        "    fontWeight: 700",
        "    lineHeight: 1.1",
        "  body-md:",
        f"    fontFamily: {_quote(body_font)}",
        "    fontSize: 16px",
        "    fontWeight: 400",
        "    lineHeight: 1.6",
        "rounded:",
    ]
    lines += [f"  {key}: {value}" for key, value in rounded.items()]
    lines.append("spacing:")
    lines += [f"  {key}: {value}" for key, value in SPACING_SCALE.items()]
    lines += [
        "components:",
        "  button-primary:",
        '    backgroundColor: "{colors.primary}"',
        f'    textColor: "{on_primary}"',
        '    rounded: "{rounded.md}"',
        "    padding: 12px",
        "  card:",
        f'    backgroundColor: "{{colors.{"surface" if "surface" in colors else "neutral"}}}"',
        '    textColor: "{colors.ink}"',
        '    rounded: "{rounded.md}"',
        "    padding: 24px",
        "---",
        "",
        f"# {name}",
        "",
        "## Overview",
        f"Draft built from {source}. State who this is for and what it must feel like before building on it.",
        "",
        "## Colors",
        "Values were read, not designed. Say what each colour is for and where it must never appear.",
        "",
        "## Typography",
        f"Body: {body_font}. Headings: {heading_font}. The scale and weights are defaults to review.",
        "",
        "## Page Composition",
        "Not read from the page. Write the order of the sections, what each is for and why, one bullet per decision with its reason.",
        "",
        "## Imagery and Icons",
        "Not read from the page. Say where every picture comes from (the brand folder first, then a licensed photograph, a drawn SVG) and the style rules.",
        "",
        "## Motion and Interaction",
        "Not read from the page. Say what moves and what stays still, the durations, and the hover, focus and loading states, each with its reason.",
        "",
        "## Responsive Behavior",
        "Not read from the page. Say what collapses at 375, 768 and 1280 px.",
        "",
        "## Accessibility",
        "Not read from the page. Say the contrast pairs, the focus order, the touch targets and the reduced-motion rule.",
        "",
        "## Do's and Don'ts",
        "- Write four to eight rules a reviewer can check by looking at the page.",
        "",
        "## Known Gaps",
    ]
    lines += [f"- {gap}" for gap in gaps] or [
        "- Component details, spacing and motion were not read; they are defaults."
    ]
    if found.max_width:
        lines.append(f"- Content width seen: about {int(found.max_width)}px.")
    if found.gradients:
        lines.append(
            f"- The source uses gradients ({found.gradients} elements); the draft has no gradient tokens."
        )
    return "\n".join(lines) + "\n"


def _quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def css_from_project(files: dict[str, str]) -> Extracted:
    """Merge the tokens of several CSS files (a theme file, an index.css) into one draft input."""
    merged = Extracted()
    for _, text in sorted(files.items()):
        part = from_css(text)
        for role, value in part.colors.items():
            merged.colors.setdefault(role, value)
        merged.fonts += [f for f in part.fonts if f not in merged.fonts]
        merged.heading_font = merged.heading_font or part.heading_font
        merged.radii = sorted(set(merged.radii) | set(part.radii))
    if not merged.colors and not merged.fonts:
        raise DesignMdError(
            "No design tokens (CSS custom properties or a Tailwind @theme block) were found in the project's style files"
        )
    return merged
