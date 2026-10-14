"""One brand file for every document the model builds (TODO W4, D-347): a JSON file with the company colours and fonts."""

from __future__ import annotations

from pydantic import Field

from forge.brand.kit import BrandError, BrandKit, Resolved, parse_brand
from forge.errors import ForgeError
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

BRAND_FILE_DESCRIPTION = (
    "Optional path of a brand JSON file (accent, text, background, title_font, body_font ...: the same file serves decks, Word, Excel and PDF); "
    "its colours and fonts replace the outline's own `brand`. Or `theme:<name>` to use one of the deck themes (clean, dark, ocean ...: the same names and "
    "contrast-checked colours as presentations), so a report and its deck match. Empty: the project's saved brand.json (see save_brand) when there is one"
)
THEME_PREFIX = "theme:"
DEFAULT_BRAND_FILE = "brand.json"  # saved by save_brand; used when a build names no brand file


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
        saved = context.workspace.path_of(DEFAULT_BRAND_FILE)
        if saved.is_file():
            try:
                return parse_brand(saved.read_text(encoding="utf-8"))
            except (BrandError, OSError, ValueError):
                return None  # a brand.json that is not ours (an unrelated file of a copied repository) is ignored
        return None
    if path.lower().startswith(THEME_PREFIX):
        return theme_kit(path[len(THEME_PREFIX) :])
    file = context.workspace.path_of(path)
    if not file.is_file():
        raise BrandError(f"No brand file at {path}.")
    return parse_brand(file.read_text(encoding="utf-8"))


class SaveBrand(Tool):
    name = "save_brand"
    read_only = False
    description = (
        "Save the company look once, as brand.json in the project: the colours and fonts (six-digit hex colours) or a deck theme to start from. Every deck, Word, "
        "Excel and PDF built afterwards uses it unless a build names another brand file, so the documents of one project match. Give what you know; the rest is derived and "
        "checked for contrast."
    )

    class Args(ToolArgs):
        theme: str = Field(
            default="",
            description="Start from a deck theme (clean, dark, ocean ...); the colours below replace its own",
        )
        accent: str | None = None
        text: str | None = None
        background: str | None = None
        muted: str | None = None
        surface: str | None = None
        accent_text: str | None = None
        title_font: str | None = None
        body_font: str | None = None
        reason: str = Field(default="", description="One line saying why; shown to the user in CHANGES.md.")

    def summary(self, args: SaveBrand.Args) -> str:
        return "save brand" + (f" from theme {args.theme}" if args.theme else "")

    async def run(self, args: SaveBrand.Args, context: ToolContext) -> ToolResult:
        try:
            base = theme_kit(args.theme).model_dump(exclude_none=True) if args.theme else {}
            given = args.model_dump(exclude={"theme", "reason"}, exclude_none=True)
            kit = BrandKit.model_validate({**base, **given})
        except (BrandError, ForgeError, ValueError) as error:
            return ToolResult(ok=False, content=f"The brand is not valid: {str(error)[:400]}")
        if not kit.model_dump(exclude_none=True):
            return ToolResult(
                ok=False, content="Give a theme or at least an accent colour, a text colour or a font."
            )
        context.workspace.write_text(
            DEFAULT_BRAND_FILE,
            kit.model_dump_json(exclude_none=True, indent=2) + chr(10),
            args.reason or "company look saved",
        )
        resolved = Resolved(kit)
        context.last_edit_step = context.step
        return ToolResult(
            ok=True,
            content=(
                f"Saved {DEFAULT_BRAND_FILE}. Used by every build that names no brand file. On white paper: text {resolved.text or 'default'}, headings {resolved.heading or 'default'}, "
                f"table headers {resolved.header_fill or 'default'} with {resolved.header_text or 'default'} text."
            ),
        )
