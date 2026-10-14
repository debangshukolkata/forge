"""The brand kit and the colour maths behind it (D-347)."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

from forge.errors import ForgeError

HexColour = Annotated[str, StringConstraints(pattern=r"^#?[0-9A-Fa-f]{6}$")]
MIN_CONTRAST = 4.5  # WCAG AA for normal text
SAFE_PDF_FONTS = {
    "helvetica": "Helvetica",
    "arial": "Helvetica",
    "times": "Times-Roman",
    "times new roman": "Times-Roman",
    "courier": "Courier",
}


class BrandError(ForgeError):
    """The brand file is not valid; the message says what to change."""


class BrandKit(BaseModel):
    """Colours and fonts of the user's brand. Give what you know; the rest is derived so text stays readable."""

    model_config = ConfigDict(extra="forbid")

    accent: HexColour | None = None
    background: HexColour | None = None
    text: HexColour | None = None
    muted: HexColour | None = None
    surface: HexColour | None = None
    accent_text: HexColour | None = None
    title_font: str | None = None
    body_font: str | None = None


def clean(colour: str) -> str:
    return colour.lstrip("#").upper()


def _channels(colour: str) -> tuple[float, float, float]:
    value = clean(colour)
    return int(value[0:2], 16) / 255, int(value[2:4], 16) / 255, int(value[4:6], 16) / 255


def luminance(colour: str) -> float:
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in _channels(colour)]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    a, b = sorted((luminance(first), luminance(second)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def mix(first: str, second: str, share: float) -> str:
    """`share` of `second` blended into `first`."""
    one, two = _channels(first), _channels(second)
    return "".join(f"{round((x * (1 - share) + y * share) * 255):02X}" for x, y in zip(one, two, strict=True))


def readable_on(background: str) -> str:
    """White or near-black, whichever reads better on `background`."""
    return "FFFFFF" if contrast("FFFFFF", background) >= contrast("111111", background) else "111111"


def darken_until_readable(colour: str, background: str = "FFFFFF", ratio: float = MIN_CONTRAST) -> str:
    """`colour` moved toward black (on a light background) or white (on a dark one) until it meets `ratio`."""
    target = "000000" if luminance(background) > 0.4 else "FFFFFF"
    result = clean(colour)
    for step in range(1, 21):
        if contrast(result, background) >= ratio:
            return result
        result = mix(clean(colour), target, step * 0.05)
    return result


def parse_brand(text: str) -> BrandKit:
    try:
        return BrandKit.model_validate_json(text)
    except (ValueError, ValidationError) as error:
        raise BrandError(
            f"The brand file is not valid: {str(error)[:400]}. Use a JSON object with accent, text, title_font, body_font ... "
            "(six-digit colours such as 1F3864)."
        ) from error


class Resolved:
    """What a document builder needs from a brand kit, with every colour checked for contrast on white paper."""

    def __init__(self, kit: BrandKit | None) -> None:
        kit = kit or BrandKit()
        self.accent = clean(kit.accent) if kit.accent else None
        self.text = darken_until_readable(kit.text) if kit.text else None
        self.heading = darken_until_readable(kit.accent) if kit.accent else self.text
        self.header_fill = self.accent
        self.header_text = readable_on(self.accent) if self.accent else None
        self.title_font = kit.title_font
        self.body_font = kit.body_font or kit.title_font

    def pdf_font(self, name: str | None, bold: bool = False) -> str:
        """A PDF's standard fonts only: the closest of Helvetica, Times and Courier to the brand font."""
        base = SAFE_PDF_FONTS.get((name or "").lower(), "Helvetica")
        if bold:
            return {"Helvetica": "Helvetica-Bold", "Times-Roman": "Times-Bold", "Courier": "Courier-Bold"}[
                base
            ]
        return base
