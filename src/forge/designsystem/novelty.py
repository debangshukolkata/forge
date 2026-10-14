"""How different two design systems really are (D-350).

A "new" design that only changes the accent colour is the same design. The fingerprint reads seven dimensions from a DESIGN.md; two systems
count as different when they differ on at least three of them (the rule of the creative second round, and of the three candidates of the first)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from forge.designsystem.colour import hue_and_saturation, parse
from forge.designsystem.spec import DesignSystem

MIN_DIFFERENT_DIMENSIONS = 3
DIMENSIONS = ("tone", "accent hue", "display font", "corner style", "density", "layout energy", "composition")
HUE_NAMES = (
    (15, "red"),
    (45, "orange"),
    (70, "yellow"),
    (160, "green"),
    (200, "cyan"),
    (255, "blue"),
    (290, "purple"),
    (335, "pink"),
    (360, "red"),
)


@dataclass(frozen=True)
class Fingerprint:
    tone: str  # "dark" or "light"
    accent_hue: str  # "red", "blue", ... or "neutral" when the accent has no colour
    display_font: str
    corner_style: str  # "sharp", "soft", "round" or "pill"
    density: str  # "airy", "balanced" or "dense" ("" when the file gives no dial)
    energy: str  # "calm", "balanced" or "bold" ("" when the file gives no dial)
    composition: str = ""  # the layout recipe the design is built on (`composition:` in the front matter), "" when none is named

    def values(self) -> tuple[str, ...]:
        return (
            self.tone,
            self.accent_hue,
            self.display_font,
            self.corner_style,
            self.density,
            self.energy,
            self.composition,
        )


def _band(value: object, low: int, high: int, names: tuple[str, str, str]) -> str:
    try:
        number = float(str(value))
    except ValueError:
        return ""
    return names[0] if number <= low else (names[2] if number >= high else names[1])


def _pixels(value: object) -> float | None:
    text = str(value).strip().lower()
    for unit, scale in (("px", 1.0), ("rem", 16.0), ("em", 16.0)):
        if text.endswith(unit):
            try:
                return float(text[: -len(unit)]) * scale
            except ValueError:
                return None
    return None


def _first_saturated(system: DesignSystem) -> str:
    for value in system.colors.values():
        resolved = str(system.resolve(value))
        measured = hue_and_saturation(resolved)
        if measured and measured[1] >= 0.15:
            return resolved
    return ""


def _display_style(system: DesignSystem) -> Any:
    """The typography token that carries the display voice: one named display, headline, h1, title or hero, else the one with the largest size."""
    for name in ("display", "headline", "h1", "hero", "title"):
        if isinstance(system.typography.get(name), dict):
            return system.typography[name]
    styles = [s for s in system.typography.values() if isinstance(s, dict)]
    sized = [(_pixels(system.resolve(s.get("fontSize", ""))) or 0.0, s) for s in styles]
    return max(sized, key=lambda pair: pair[0])[1] if sized else {}


def fingerprint(system: DesignSystem) -> Fingerprint:
    colours = system.colors
    background = next(
        (
            system.resolve(colours[k])
            for k in ("neutral", "canvas", "background", "surface", "bg")
            if k in colours
        ),
        "#FFFFFF",
    )
    parsed = parse(str(background)) or (255, 255, 255, 1.0)
    tone = "dark" if (0.2126 * parsed[0] + 0.7152 * parsed[1] + 0.0722 * parsed[2]) < 110 else "light"
    accent = system.resolve(
        colours.get("primary") or colours.get("accent") or _first_saturated(system) or "#808080"
    )
    measured = hue_and_saturation(str(accent))
    if measured is None or measured[1] < 0.15:
        hue_name = "neutral"
    else:
        hue_name = next(name for limit, name in HUE_NAMES if measured[0] <= limit)
    display = _display_style(system)
    family = str(system.resolve(display.get("fontFamily", ""))) if isinstance(display, dict) else ""
    font = family.split(",")[0].strip().strip("\"'").lower()
    radii = [
        r
        for r in (_pixels(system.resolve(v)) for k, v in system.rounded.items() if k not in ("pill", "full"))
        if r is not None
    ]
    biggest = max(radii) if radii else None
    if "pill" in system.rounded or "full" in system.rounded:
        corner = "pill" if biggest is None or biggest < 20 else "round"
    elif biggest is None:
        corner = ""
    else:
        corner = "sharp" if biggest < 5 else ("soft" if biggest < 14 else "round")
    raw_dials = system.extra.get("dials")
    dials: dict[str, Any] = raw_dials if isinstance(raw_dials, dict) else {}
    return Fingerprint(
        tone,
        hue_name,
        font,
        corner,
        _band(dials.get("density"), 3, 7, ("airy", "balanced", "dense")),
        _band(dials.get("variance"), 3, 7, ("calm", "balanced", "bold")),
        str(system.extra.get("composition", "") or "").strip().lower(),
    )


def differences(first: Fingerprint, second: Fingerprint) -> list[str]:
    """The dimensions on which both files say something and say different things."""
    return [
        name
        for name, one, two in zip(DIMENSIONS, first.values(), second.values(), strict=True)
        if one and two and one != two
    ]


def is_different_enough(first: Fingerprint, second: Fingerprint) -> bool:
    return len(differences(first, second)) >= MIN_DIFFERENT_DIMENSIONS


def describe_fingerprint(print_: Fingerprint) -> str:
    parts = [
        print_.tone,
        f"{print_.accent_hue} accent",
        print_.display_font or "no display font",
        f"{print_.corner_style or '?'} corners",
    ]
    if print_.density:
        parts.append(print_.density)
    if print_.energy:
        parts.append(print_.energy)
    if print_.composition:
        parts.append(f"composition {print_.composition}")
    return ", ".join(parts)
