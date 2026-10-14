"""One application-screen recipe: what the catalogue says about it and how the file is built (D-366)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Screen:
    id: str  # catalogue id, also the file name: app-<id>
    title: str
    summary: str
    palette: str
    font: str
    css: str
    body: str
    icons: list[str]
    moods: list[str]
    products: list[str]
    density: str
    tags: list[str]
    extra_root: str = ""
    uses: str = ""  # one line: when to pick this screen
    notes: list[str] = field(default_factory=list)
