"""One brand file for every document the model builds (TODO W4, D-347): a JSON file with the company colours and fonts."""

from __future__ import annotations

from forge.brand.kit import BrandError, BrandKit, parse_brand
from forge.toolkit.base import ToolContext

BRAND_FILE_DESCRIPTION = (
    "Optional path of a brand JSON file (accent, text, background, title_font, body_font ...: the same file serves decks, Word, Excel and PDF); "
    "its colours and fonts replace the outline's own `brand`"
)


def load_brand_file(context: ToolContext, path: str) -> BrandKit | None:
    if not path:
        return None
    file = context.workspace.path_of(path)
    if not file.is_file():
        raise BrandError(f"No brand file at {path}.")
    return parse_brand(file.read_text(encoding="utf-8"))
