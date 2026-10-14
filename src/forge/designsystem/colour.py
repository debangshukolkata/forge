"""CSS colours for design tokens (D-348): parse the common forms, measure contrast and hue."""

from __future__ import annotations

import colorsys
import re

from forge.brand.kit import contrast as hex_contrast

NAMED = {
    "white": "ffffff",
    "black": "000000",
    "red": "ff0000",
    "green": "008000",
    "blue": "0000ff",
    "yellow": "ffff00",
    "orange": "ffa500",
    "purple": "800080",
    "gray": "808080",
    "grey": "808080",
    "silver": "c0c0c0",
    "navy": "000080",
    "teal": "008080",
    "pink": "ffc0cb",
    "transparent": "000000",
}
HEX = re.compile(r"^#?([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
FUNCTION = re.compile(r"^(rgba?|hsla?)\(\s*([^)]+)\)$", re.I)


def _number(text: str, scale: float) -> float:
    text = text.strip()
    return float(text[:-1]) / 100 * scale if text.endswith("%") else float(text)


def parse(text: str) -> tuple[int, int, int, float] | None:
    """(red, green, blue, alpha) of a CSS colour, or None when the form is not understood (oklch, color-mix, var()...)."""
    value = str(text).strip().lower()
    if value in NAMED:
        digits = NAMED[value]
        return (
            int(digits[0:2], 16),
            int(digits[2:4], 16),
            int(digits[4:6], 16),
            0.0 if value == "transparent" else 1.0,
        )
    match = HEX.match(value)
    if match:
        digits = match.group(1)
        if len(digits) in (3, 4):
            digits = "".join(c * 2 for c in digits)
        alpha = int(digits[6:8], 16) / 255 if len(digits) == 8 else 1.0
        return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16), alpha
    function = FUNCTION.match(value)
    if not function:
        return None
    parts = [p for p in re.split(r"[\s,/]+", function.group(2).strip()) if p]
    try:
        if function.group(1).startswith("rgb"):
            red, green, blue = (round(_number(p, 255)) for p in parts[:3])
        else:
            hue = float(parts[0].removesuffix("deg")) % 360 / 360
            saturation, lightness = _number(parts[1], 1), _number(parts[2], 1)
            r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
            red, green, blue = round(r * 255), round(g * 255), round(b * 255)
        alpha = _number(parts[3], 1) if len(parts) > 3 else 1.0
    except (ValueError, IndexError):
        return None
    return max(0, min(255, red)), max(0, min(255, green)), max(0, min(255, blue)), alpha


def to_hex(colour: tuple[int, int, int, float]) -> str:
    return "{:02X}{:02X}{:02X}".format(*colour[:3])


def contrast(first: str, second: str) -> float | None:
    """WCAG contrast ratio of two CSS colours; None when either is not an opaque, understood colour."""
    one, two = parse(first), parse(second)
    if one is None or two is None or one[3] < 1 or two[3] < 1:
        return None
    return hex_contrast(to_hex(one), to_hex(two))


def hue_and_saturation(colour: str) -> tuple[float, float, float] | None:
    """(hue in degrees, saturation 0-1, lightness 0-1) of a colour, or None."""
    parsed = parse(colour)
    if parsed is None:
        return None
    hue, lightness, saturation = colorsys.rgb_to_hls(parsed[0] / 255, parsed[1] / 255, parsed[2] / 255)
    return hue * 360, saturation, lightness
