"""The looks a deck can have (D-240, D-281). Fonts are ones every Windows and Mac Office install has (Calibri, Georgia), so
the deck looks the same on the reader's computer. Every theme is checked for contrast by tests (text on its background and
on cards, muted text, text on the accent), so a deck is readable whichever one is chosen. A deck may also carry a brand kit
(`Brand`) that overrides colours and fonts; the missing colours are derived so the result stays readable.

Choose by the audience and the topic, not by habit: `suggest_themes("charity blood donation")` ranks the themes."""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Theme:
    name: str
    background: str  # hex without '#'
    surface: str  # cards and table stripes
    text: str
    muted: str
    accent: str
    accent_text: str  # text drawn on the accent colour
    palette: tuple[str, ...]  # chart series colours, in order; the first is the accent
    title_font: str = "Calibri"  # on every Windows and Mac Office install (P1.7); bold is applied to titles
    body_font: str = "Calibri"
    mood: str = ""  # a few words for choosing
    topics: tuple[str, ...] = ()  # words that suggest this theme
    dark: bool = False


# --- colour maths (WCAG 2 relative luminance) ---


def _channels(hex_colour: str) -> tuple[float, float, float]:
    return tuple(int(hex_colour[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def luminance(hex_colour: str) -> float:
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in _channels(hex_colour)]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    a, b = sorted((luminance(first), luminance(second)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def mix(first: str, second: str, share: float) -> str:
    """`first` moved `share` (0 to 1) of the way toward `second`."""
    a, b = _channels(first), _channels(second)
    return "".join(f"{round((x + (y - x) * share) * 255):02X}" for x, y in zip(a, b, strict=True))


def readable_on(background: str) -> str:
    """Near-black or white, whichever reads better on `background`."""
    return "111827" if contrast("111827", background) >= contrast("FFFFFF", background) else "FFFFFF"


def _toward_contrast(colour: str, background: str, towards: str, minimum: float) -> str:
    """`colour` moved toward `towards` until it reaches `minimum` contrast against `background`."""
    for step in range(0, 21):
        candidate = mix(colour, towards, step / 20)
        if contrast(candidate, background) >= minimum:
            return candidate
    return towards


CHART_CONTRAST = 3.0  # chart colours must stand out from the slide background (WCAG graphics guidance)


def _chart_colours(palette: list[str], background: str, text: str) -> tuple[str, ...]:
    """The series colours, each nudged toward the text colour only as far as needed to reach CHART_CONTRAST."""
    return tuple(_toward_contrast(c, background, text, CHART_CONTRAST) for c in palette)


def _theme(
    name: str, colours: str, palette: str, mood: str, topics: str, *, serif: bool = False, dark: bool = False
) -> Theme:
    background, surface, text, muted, accent, accent_text = colours.split()
    return Theme(
        name=name,
        background=background,
        surface=surface,
        text=text,
        muted=muted,
        accent=accent,
        accent_text=accent_text,
        palette=_chart_colours(palette.split(), background, text),
        title_font="Georgia" if serif else "Calibri",
        mood=mood,
        topics=tuple(topics.split()),
        dark=dark,
    )


THEMES: dict[str, Theme] = {
    t.name: t
    for t in (
        _theme(
            "clean",
            "FFFFFF F1F4F9 1B2430 5B6675 1F5FBF FFFFFF",
            "1F5FBF E08A1E 2E8B6A B5446E 6B5BD2 5B6675",
            "neutral, crisp, business",
            "business report update general status quarterly",
        ),
        _theme(
            "dark",
            "0F1B2D 1B2B44 F2F5FA AEBBCE 5AA2FF 0F1B2D",
            "5AA2FF FFB454 5FD3A5 F27BA3 A99BFF AEBBCE",
            "dark, focused, technical",
            "keynote product launch demo evening",
            dark=True,
        ),
        _theme(
            "warm",
            "FBF6EE F1E7D6 2B2118 6E5E4D B4532A FFFFFF",
            "B4532A 2F6F73 D79A2B 7A4E9C 4E7F3A 6E5E4D",
            "warm, human, editorial",
            "story people community culture",
            serif=True,
        ),
        _theme(
            "forest",
            "F7FAF5 E6EFE2 1B2A1F 4F6354 2F6B3C FFFFFF",
            "2F6B3C D9A441 3E7C8C A4553A 7A6BB0 4F6354",
            "natural, calm, grounded",
            "sustainability nature agriculture environment green climate outdoors",
            serif=True,
        ),
        _theme(
            "ocean",
            "F4FAFB DCEEF1 12303A 4A6670 0B6E7F FFFFFF",
            "0B6E7F E4893B 3C6FB8 B24C63 6C9A3F 4A6670",
            "fresh, clear, open",
            "travel water marine shipping logistics coastal wellness",
        ),
        _theme(
            "sunset",
            "FFF8F3 FDE9DC 2E1A14 6B4A3A C2410C FFFFFF",
            "C2410C 5B3FD0 1F7A8C B8860B 3D8A4D 6B4A3A",
            "energetic, creative, friendly",
            "marketing creative events consumer brand campaign",
        ),
        _theme(
            "slate",
            "F8F9FB E9ECF1 1F2733 566072 3B4A63 FFFFFF",
            "3B4A63 B7791F 2C7A7B 9B2C2C 5A67D8 566072",
            "formal, sober, trustworthy",
            "finance legal consulting government audit compliance board",
        ),
        _theme(
            "midnight",
            "0B1220 16213A F3F0E8 B5BDCB E0B04C 0B1220",
            "E0B04C 6FB1E8 7BD0B0 E88FA8 B79CF0 B5BDCB",
            "premium, serious, confident",
            "premium luxury investor finance executive strategy",
            dark=True,
        ),
        _theme(
            "paper",
            "FBF7F0 EFE8DA 24211C 66604F 7A1F2B FFFFFF",
            "7A1F2B 2F5D62 B8860B 5B4B8A 4E7A3A 66604F",
            "editorial, scholarly, calm",
            "education research humanities books history lecture academic",
            serif=True,
        ),
        _theme(
            "mint",
            "F3FBF8 DDF1EA 17302A 477066 12805C FFFFFF",
            "12805C E2674F 3D7FB3 C2972A 8461B0 477066",
            "healthy, light, caring",
            "health wellness hospital nutrition clinic care medical",
        ),
        _theme(
            "plum",
            "FAF5F9 EEDFEA 2A1630 6B4F73 7B2D82 FFFFFF",
            "7B2D82 D1913C 2E7D8C B23A5E 5B7A3A 6B4F73",
            "expressive, cultural, refined",
            "arts culture fashion beauty museum theatre design",
        ),
        _theme(
            "terracotta",
            "FAF4EF F0E1D5 2B1E17 6F5547 A8442A FFFFFF",
            "A8442A 3F7A74 C9962F 6B4E8E 5F7F3C 6F5547",
            "earthy, crafted, welcoming",
            "architecture craft food hospitality interiors restaurant",
            serif=True,
        ),
        _theme(
            "mono",
            "FFFFFF F1F1F1 111111 555555 111111 FFFFFF",
            "111111 767676 A8A8A8 C62828 1F5FBF D79A2B",
            "minimal, stark, modern",
            "minimal architecture design portfolio photography studio",
        ),
        _theme(
            "sky",
            "F5F9FF E0ECFB 14263F 4B607C 1D6FD6 FFFFFF",
            "1D6FD6 F08A24 22966E C2456B 6C5CE0 4B607C",
            "open, friendly, technical",
            "technology education saas startup software training",
        ),
        _theme(
            "coral",
            "FFF7F5 FFE4DE 331A1A 7B4C4C D03F37 FFFFFF",
            "D03F37 2A8C82 E6A526 6C4DB8 3F7FBF 7B4C4C",
            "playful, bright, approachable",
            "kids children food retail playful family",
        ),
        _theme(
            "graphite",
            "14171C 1F242C ECEFF3 A9B1BD B6E35A 14171C",
            "B6E35A 5FB3F5 F5A65F F27B9C A58BF2 A9B1BD",
            "technical, sharp, modern",
            "developer engineering data ai code platform architecture",
            dark=True,
        ),
        _theme(
            "ruby",
            "FFF8F8 FBE4E4 2A1213 7A4A4C B3202C FFFFFF",
            "B3202C 2D6A8F C98A1B 5C7A3A 7B4FA0 7A4A4C",
            "urgent, human, committed",
            "charity health donation emergency fundraising nonprofit blood",
        ),
        _theme(
            "olive",
            "F8F8F1 E8E8D8 25281A 5E634A 5E6B1F FFFFFF",
            "5E6B1F B7662B 2F6B73 8A3B4E 6A5BA0 5E634A",
            "grounded, heritage, quiet",
            "heritage outdoors farming craft rural conservation",
            serif=True,
        ),
        _theme(
            "indigo",
            "1A1740 262361 F2F1FF B9B6E8 8E86FF 1A1740",
            "8E86FF FFB86B 6FD6C0 FF8FB1 7BC4FF B9B6E8",
            "bold, imaginative, night",
            "ai creative events gaming music launch",
            dark=True,
        ),
    )
}


@dataclass(frozen=True)
class Brand:
    """A brand kit: any of these overrides the theme; the rest is derived so text stays readable."""

    accent: str | None = None
    background: str | None = None
    text: str | None = None
    muted: str | None = None
    surface: str | None = None
    accent_text: str | None = None
    title_font: str | None = None
    body_font: str | None = None


def apply_brand(theme: Theme, brand: Brand) -> tuple[Theme, list[str]]:
    """The theme with the brand kit applied and the derived colours filled in; also the contrast problems left."""
    background = brand.background or theme.background
    text = brand.text or (theme.text if not brand.background else readable_on(background))
    dark = luminance(background) < 0.2
    surface = brand.surface or (mix(background, text, 0.08) if brand.background else theme.surface)
    muted = brand.muted or (
        _toward_contrast(mix(text, background, 0.35), background, text, 4.5)
        if brand.background or brand.text
        else theme.muted
    )
    accent = brand.accent or theme.accent
    accent_text = brand.accent_text or readable_on(accent)
    palette = (accent, *theme.palette[1:])
    result = replace(
        theme,
        name=f"{theme.name}+brand",
        background=background,
        surface=surface,
        text=text,
        muted=muted,
        accent=accent,
        accent_text=accent_text,
        palette=palette,
        title_font=brand.title_font or theme.title_font,
        body_font=brand.body_font or theme.body_font,
        dark=dark,
    )
    return result, contrast_problems(result)


MINIMUMS = (
    ("text", "background", 4.5),
    ("text", "surface", 4.5),
    ("muted", "background", 4.5),
    ("muted", "surface", 4.5),
    ("accent_text", "accent", 4.5),
    ("accent", "background", 3.0),
)


def contrast_problems(theme: Theme) -> list[str]:
    """Readability problems of a theme as words, empty when every pair meets its minimum."""
    found = []
    for foreground, background, minimum in MINIMUMS:
        ratio = contrast(getattr(theme, foreground), getattr(theme, background))
        if ratio < minimum:
            found.append(f"{foreground} on {background} has contrast {ratio:.1f}:1, below {minimum:g}:1")
    return found


def suggest_themes(topic: str, limit: int = 3) -> list[str]:
    """Theme names ranked by how many of their topic words appear in `topic` (ties keep the listed order)."""
    words = {w.strip(".,;:!?").lower() for w in topic.split()}
    scored = sorted(
        (
            (len(words & set(t.topics)) + len(words & set(t.mood.replace(",", "").split())), -i, t.name)
            for i, t in enumerate(THEMES.values())
        ),
        reverse=True,
    )
    return [name for score, _, name in scored if score > 0][:limit]
