"""Inline formatting for freeform text (TODO P1.4, D-280). A text element with `"rich": true` may mix, inside one line:

    **bold**   *italic*   [link text](https://example.org)   {accent}coloured words{/}   {#C62828}hex colour{/}

Colour names are the theme names (accent, text, muted, surface, accent_text) or a hex value. Anything that does not
match stays literal text, so a stray asterisk never breaks a slide. Pure functions; the builder turns the runs into
PowerPoint runs."""

from __future__ import annotations

import re
from dataclasses import dataclass

TOKEN = re.compile(
    r"\*\*(?P<bold>.+?)\*\*"
    r"|\*(?P<italic>[^*\s][^*]*?)\*"
    r"|\[(?P<label>[^\]]+)\]\((?P<url>https?://[^)\s]+|mailto:[^)\s]+)\)"
    r"|\{(?P<colour>[a-z_]+|#[0-9A-Fa-f]{6})\}(?P<coloured>.+?)\{/\}"
)


@dataclass(frozen=True)
class RunSpec:
    text: str
    bold: bool = False
    italic: bool = False
    colour: str | None = None  # a theme name or "#RRGGBB"
    link: str | None = None


def parse_runs(line: str) -> list[RunSpec]:
    """The runs of one line, in order. Nested markup (bold inside colour) is read one level deep."""
    runs: list[RunSpec] = []
    position = 0
    for match in TOKEN.finditer(line):
        if match.start() > position:
            runs.append(RunSpec(line[position : match.start()]))
        if match.group("bold") is not None:
            inner = parse_runs(match.group("bold"))
            runs.extend(RunSpec(r.text, True, r.italic, r.colour, r.link) for r in inner)
        elif match.group("italic") is not None:
            runs.append(RunSpec(match.group("italic"), italic=True))
        elif match.group("label") is not None:
            runs.append(RunSpec(match.group("label"), link=match.group("url")))
        else:
            inner = parse_runs(match.group("coloured"))
            runs.extend(RunSpec(r.text, r.bold, r.italic, match.group("colour"), r.link) for r in inner)
        position = match.end()
    if position < len(line):
        runs.append(RunSpec(line[position:]))
    return runs or [RunSpec("")]


def plain_text(line: str) -> str:
    """The text of a line without its markup (what the reader sees), for measuring."""
    return "".join(run.text for run in parse_runs(line))
