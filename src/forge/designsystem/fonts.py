"""The fonts that ship with DebCraft, embedded in specimens so a candidate is judged in its real typeface (D-352).

A family that is not bundled is not embedded: the specimen shows a fallback and the tool says so, because judging type in a fallback is judging
the wrong thing."""

from __future__ import annotations

import base64
import re
from pathlib import Path

FONT_FOLDER = Path(__file__).resolve().parents[1] / "skills" / "ui-design-quality" / "fonts"


def slug(family: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", family.lower()).strip("-")


def bundled_file(family: str) -> Path | None:
    folder = FONT_FOLDER / slug(family)
    if not folder.is_dir():
        return None
    return next(iter(sorted(folder.glob("*latin-wght-normal.woff2"))), None) or next(
        iter(sorted(folder.glob("*.woff2"))), None
    )


def font_css(families: list[str]) -> tuple[str, list[str]]:
    """(an @font-face block for every bundled family in `families`, the families that are not bundled)."""
    css: list[str] = []
    missing: list[str] = []
    for family in dict.fromkeys(f for f in families if f):
        file = bundled_file(family)
        if file is None:
            missing.append(family)
            continue
        data = base64.b64encode(file.read_bytes()).decode("ascii")
        css.append(
            f'@font-face{{font-family:"{family}";src:url(data:font/woff2;base64,{data}) format("woff2");font-weight:100 900;font-style:normal}}'
        )
    return "\n".join(css), missing
