"""One brand file for every document the model builds (TODO W4, D-347): a JSON file with the company colours and fonts."""

from __future__ import annotations

from forge.brand.kit import BrandError, BrandKit, parse_brand
from forge.toolkit.base import ToolContext

BRAND_FILE_DESCRIPTION = (
    "Optional path of a brand JSON file (accent, text, background, title_font, body_font ...: the same file serves decks, Word, Excel and PDF); "
    "its colours and fonts replace the outline's own `brand`. Or `theme:<name>` to use one of the deck themes (clean, dark, ocean ...: the same names and "
    "contrast-checked colours as presentations), so a report and its deck match"
)
THEME_PREFIX = "theme:"


def theme_kit(name: str) -> BrandKit:
    """A deck theme (D-375) as a brand kit, so documents and decks share one list of looks."""
    from forge.slides.themes import THEMES

    theme = THEMES.get(name.strip().lower())
    if theme is None:
        raise BrandError(f"No theme {name!r}. Themes: {', '.join(sorted(THEMES))}.")
    if theme.dark:  # documents are printed on white paper: a dark deck theme keeps its accent and fonts, the page and text colours turn light and dark
        background, text, muted, surface = "FFFFFF", "1F2937", "5B6675", "F1F4F9"
    else:
        background, text, muted, surface = theme.background, theme.text, theme.muted, theme.surface
    return BrandKit(
        accent=theme.accent,
        background=background,
        text=text,
        muted=muted,
        surface=surface,
        accent_text=theme.accent_text,
        title_font=theme.title_font,
        body_font=theme.body_font,
    )


def load_brand_file(context: ToolContext, path: str) -> BrandKit | None:
    if not path:
        return None
    if path.lower().startswith(THEME_PREFIX):
        return theme_kit(path[len(THEME_PREFIX) :])
    file = context.workspace.path_of(path)
    if not file.is_file():
        raise BrandError(f"No brand file at {path}.")
    return parse_brand(file.read_text(encoding="utf-8"))
