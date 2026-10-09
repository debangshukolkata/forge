"""The looks a deck can have (D-240). Fonts are ones every Windows and Mac Office install has, so the deck
looks the same on the reader's computer. Colours were picked for contrast (text on its background)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    background: str  # hex without '#'
    surface: str  # cards and table stripes
    text: str
    muted: str
    accent: str
    accent_text: str  # text drawn on the accent colour
    palette: tuple[str, ...]  # chart series colours, in order
    title_font: str = "Segoe UI Semibold"
    body_font: str = "Segoe UI"


THEMES: dict[str, Theme] = {
    "clean": Theme(
        name="clean",
        background="FFFFFF",
        surface="F1F4F9",
        text="1B2430",
        muted="5B6675",
        accent="1F5FBF",
        accent_text="FFFFFF",
        palette=("1F5FBF", "E08A1E", "2E8B6A", "B5446E", "6B5BD2", "5B6675"),
    ),
    "dark": Theme(
        name="dark",
        background="0F1B2D",
        surface="1B2B44",
        text="F2F5FA",
        muted="AEBBCE",
        accent="5AA2FF",
        accent_text="0F1B2D",
        palette=("5AA2FF", "FFB454", "5FD3A5", "F27BA3", "A99BFF", "AEBBCE"),
    ),
    "warm": Theme(
        name="warm",
        background="FBF6EE",
        surface="F1E7D6",
        text="2B2118",
        muted="6E5E4D",
        accent="B4532A",
        accent_text="FFFFFF",
        palette=("B4532A", "2F6F73", "D79A2B", "7A4E9C", "4E7F3A", "6E5E4D"),
        title_font="Georgia",
        body_font="Calibri",
    ),
}
