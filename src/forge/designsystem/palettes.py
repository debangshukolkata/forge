"""Colour palettes the user can choose from for an office app (D-490), and the edit that applies one to a DESIGN.md.

The office design (D-489) is one accent on neutral surfaces, so the palette is a single decision: the colour of filled controls (`primary`, white text on it) and
the colour of bars, underlines, rings and icon tints (`brand`, never used for text on white). Nine palettes are offered; every one passes 4.5 to 1 for white text on
its `primary` except the bright orange the first user asked for by name, which is offered with its contrast stated and, when chosen, recorded in the DESIGN.md as
`contrast-accepted` so the lint and the audit leave the owner's decision alone instead of rewriting it."""

from __future__ import annotations

import re
from dataclasses import dataclass

from forge.brand.kit import contrast as hex_contrast
from forge.brand.kit import mix

PASSES = 4.5


@dataclass(frozen=True)
class Palette:
    id: str
    name: str
    primary: str  # filled controls, with `on_primary` text on them
    brand: str  # bars, underlines, rings, icon tints
    on_primary: str
    mood: str

    @property
    def ratio(self) -> float:
        return hex_contrast(self.on_primary, self.primary)

    @property
    def below_aa(self) -> bool:
        return self.ratio < PASSES


PALETTES: tuple[Palette, ...] = (
    Palette(
        "orange-bright",
        "Bright orange",
        "#FF7A00",
        "#FF7A00",
        "#FFFFFF",
        "warm, energetic, friendly; white text on it is below the contrast guideline",
    ),
    Palette("blue", "Blue", "#2563EB", "#2563EB", "#FFFFFF", "trusted, clear, familiar for business tools"),
    Palette("teal", "Teal", "#0F766E", "#14B8A6", "#FFFFFF", "calm, fresh, a little different"),
    Palette("indigo", "Indigo", "#4F46E5", "#6366F1", "#FFFFFF", "modern and product-like"),
    Palette(
        "green",
        "Green",
        "#15803D",
        "#22C55E",
        "#FFFFFF",
        "steady and positive; suits finance, health and field work",
    ),
    Palette("rose", "Rose", "#BE123C", "#F43F5E", "#FFFFFF", "bold and human; suits people-centred services"),
    Palette("violet", "Violet", "#6D28D9", "#8B5CF6", "#FFFFFF", "creative and distinctive"),
    Palette(
        "graphite",
        "Graphite and amber",
        "#1F2937",
        "#F59E0B",
        "#FFFFFF",
        "serious and quiet, with one warm signal",
    ),
    Palette(
        "orange-deep",
        "Deep orange",
        "#A34C00",
        "#FF7A00",
        "#FFFFFF",
        "the orange look with white text that passes contrast",
    ),
)
PAGES = (
    ("orange-bright", "blue", "teal", "indigo"),
    ("green", "rose", "violet", "graphite"),
    ("orange-deep",),
)  # four at a time: ask_user shows at most four


def palette_by_id(identifier: str) -> Palette | None:
    wanted = identifier.strip().lower().replace(" ", "-")
    return next((p for p in PALETTES if p.id == wanted), None)


def custom_palette(primary: str, brand: str = "") -> Palette | None:
    """A palette from the user's own hex colours; None when `primary` is not a six-digit hex."""
    pattern = re.compile(r"^#?([0-9a-fA-F]{6})$")
    first = pattern.match(primary.strip())
    if first is None:
        return None
    second = pattern.match(brand.strip()) if brand.strip() else None
    if brand.strip() and second is None:
        return None
    hex_primary = "#" + first.group(1).upper()
    on_primary = (
        "#FFFFFF"
        if hex_contrast("FFFFFF", first.group(1)) >= hex_contrast("111111", first.group(1))
        else "#111111"
    )
    return Palette(
        "custom",
        "Your colour",
        hex_primary,
        "#" + (second or first).group(1).upper(),
        on_primary,
        "your own colour",
    )


def _front_matter(text: str) -> tuple[str, str, str] | None:
    match = re.match(r"^(---[ \t]*\r?\n)(.*?)(\r?\n---[ \t]*(?:\r?\n|$))", text, re.DOTALL)
    return (match.group(1), match.group(2), text[match.end(2) :]) if match else None


def _set_in_block(lines: list[str], block: str, key: str, value: str, indent: str) -> None:
    """Sets `key: "value"` inside the top-level `block:` of the front matter (replacing it, or adding it as the block's last line)."""
    start = next((i for i, line in enumerate(lines) if line.rstrip() == f"{block}:"), None)
    if start is None:
        return
    end = start + 1
    while end < len(lines) and (lines[end].startswith((" ", "\t")) or not lines[end].strip()):
        end += 1
    for i in range(start + 1, end):
        if re.match(rf"^{re.escape(indent)}{re.escape(key)}\s*:", lines[i]):
            lines[i] = f'{indent}{key}: "{value}"'
            return
    last = end
    while last > start + 1 and not lines[last - 1].strip():
        last -= 1
    lines.insert(last, f'{indent}{key}: "{value}"')


def _set_component_field(lines: list[str], component: str, key: str, value: str) -> None:
    start = next((i for i, line in enumerate(lines) if line.rstrip() == f"  {component}:"), None)
    if start is None:
        return
    for i in range(start + 1, len(lines)):
        if not lines[i].startswith("    "):
            break
        if re.match(rf"^    {re.escape(key)}\s*:", lines[i]):
            lines[i] = f'    {key}: "{value}"'
            return


def apply_palette(text: str, palette: Palette) -> str:
    """The DESIGN.md with the palette's colours: `primary` and `brand` roles, the primary button's text and hover, and the `contrast-accepted` note when white text
    on the primary is below 4.5 to 1. Everything else in the file is left as it was."""
    parts = _front_matter(text)
    if parts is None:
        return text
    opening, front, rest = parts
    newline = "\r\n" if "\r\n" in front else "\n"
    lines = front.split(newline) if newline in front else front.split("\n")
    _set_in_block(lines, "colors", "primary", palette.primary, "  ")
    _set_in_block(lines, "colors", "brand", palette.brand, "  ")
    _set_component_field(lines, "button-primary", "textColor", palette.on_primary)
    hover = "#" + mix(
        palette.primary.lstrip("#"), "000000" if palette.on_primary.upper() == "#FFFFFF" else "FFFFFF", 0.15
    )
    _set_component_field(lines, "button-primary-hover", "backgroundColor", hover)
    _set_component_field(lines, "button-primary-hover", "textColor", palette.on_primary)
    lines = [line for line in lines if not line.startswith("contrast-accepted:")]
    if palette.below_aa:
        position = next((i for i, line in enumerate(lines) if line.rstrip() == "colors:"), len(lines))
        lines.insert(
            position, f'contrast-accepted: ["{palette.primary}", "{hover.upper()}"]'
        )  # the hover shade of the same button is accepted with it
    return opening + newline.join(lines) + rest


def dark_variant(palette: Palette) -> Palette:
    """The palette for a dark office design (BO7): the filled controls use the light accent (the `brand` colour lifted a little) with dark text, because a deep
    shade that carries white text on a light page is too heavy on a near-black one. Contrast is computed, not assumed."""
    lifted = "#" + mix(palette.brand.lstrip("#"), "FFFFFF", 0.12).upper()
    on_primary = (
        "#111111"
        if hex_contrast("111111", lifted.lstrip("#")) >= hex_contrast("FFFFFF", lifted.lstrip("#"))
        else "#FFFFFF"
    )
    return Palette(f"{palette.id}-dark", f"{palette.name} (dark)", lifted, lifted, on_primary, palette.mood)


def is_dark_design(text: str) -> bool:
    """True when the DESIGN.md's page colour (`neutral`, else `background`) is dark."""
    parts = _front_matter(text)
    if parts is None:
        return False
    for key in ("neutral", "background"):
        found = re.search(rf"^\s+{key}\s*:\s*[\"']?#?([0-9a-fA-F]{{6}})", parts[1], re.MULTILINE)
        if found:
            return hex_contrast("FFFFFF", found.group(1)) > 8
    return False


def accepted_backgrounds(text: str) -> list[str]:
    """Hex colours whose text contrast the owner accepted below the guideline (`contrast-accepted:` in the front matter)."""
    parts = _front_matter(text)
    if parts is None:
        return []
    for line in parts[1].splitlines():
        if line.startswith("contrast-accepted:"):
            return ["#" + m.upper() for m in re.findall(r"#?([0-9a-fA-F]{6})", line.split(":", 1)[1])]
    return []
