"""Token lint (TODO L8): static check that the project's own UI source uses its design tokens instead of
hard-coded colours, fonts and Tailwind's default palette. Shown in the screenshot audit next to the other source
findings. It only speaks when the project defines tokens (an `@theme` block or a `:root` with custom properties);
a project without tokens is the DESIGN.md gate's business, not this lint's."""

from __future__ import annotations

import re
from pathlib import Path

SKIPPED_FOLDERS = {"node_modules", "dist", "build", ".git", ".venv", "venv", "__pycache__"}
MARKUP_SUFFIXES = {".tsx", ".jsx", ".vue", ".svelte", ".html"}
STYLE_SUFFIXES = {".css", ".scss"}
MAX_FILE_BYTES = 400_000
FILES_SHOWN = 3
# A file with only one or two odd colours is usually a drawn graphic or a one-off; three or more is drift.
MIN_DISTINCT_COLOURS = 3
NEUTRAL_SPREAD = 8  # largest gap between red, green and blue that still counts as grey

COLOUR_LITERAL = re.compile(
    r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b|\b(?:rgba?|hsla?|oklch|oklab)\([^)]{3,60}\)"
)
TOKEN_DEFINITION = re.compile(r"^\s*--[\w-]+\s*:\s*([^;]+);", re.MULTILINE)
DEFINES_TOKENS = re.compile(r"@theme\b|:root\s*\{[^}]*--[\w-]+\s*:", re.DOTALL)
DEFINES_COLOUR_TOKENS = re.compile(
    r"--color-[\w-]+\s*:|--(?:accent|brand|primary|surface|bg|ink|text)[\w-]*\s*:"
)
FONT_DECLARATION = re.compile(
    r"font-family\s*:\s*([^;}\n]+)|fontFamily\s*:\s*[\"'`]([^\"'`]+)", re.IGNORECASE
)
DEFAULT_PALETTE_CLASS = re.compile(
    r"\b(?:bg|text|border|ring|outline|from|to|via|fill|stroke|divide|decoration|shadow)-"
    r"(?:red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose|"
    r"slate|gray|zinc|neutral|stone)-\d{2,3}\b"
)
# A colour that is only the fallback of a theme variable, var(--accent, #b3261e), is a token in use.
VAR_WITH_FALLBACK = re.compile(r"var\(\s*--[\w-]+\s*,\s*(?:[^()]|\([^()]*\))*\)")
GENERIC_FONT_KEYWORDS = {"inherit", "initial", "unset", "sans-serif", "serif", "monospace", "system-ui"}


def _is_neutral(literal: str) -> bool:
    """Black, white and greys (and translucent overlays of them) carry no brand decision: masks, glass, scrims."""
    hex_match = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})", literal)
    if hex_match:
        digits = hex_match.group(1)
        step = 1 if len(digits) == 3 else 2
        channels = [int(digits[i : i + step] * (2 // step), 16) for i in (0, step, 2 * step)]
    else:
        numbers = re.findall(r"\d+(?:\.\d+)?", literal) if literal.startswith("rgb") else []
        channels = [int(float(n)) for n in numbers[:3]]
        if len(channels) < 3:
            return False
    return max(channels) - min(channels) <= NEUTRAL_SPREAD


def _normal_colour(text: str) -> str:
    return re.sub(r"\s+", "", text.lower())


def _design_md_colours(root: Path) -> list[str]:
    """The hex colours of the project's DESIGN.md when it uses the token format; empty otherwise (no file, or free text)."""
    from forge.designsystem.colour import parse, to_hex
    from forge.designsystem.spec import DesignMdError, parse_design_md

    for relative in ("DESIGN.md", "design.md", "docs/DESIGN.md", "docs/design.md"):
        path = root / relative
        if path.is_file():
            try:
                system = parse_design_md(path.read_text(encoding="utf-8", errors="replace"))
            except (DesignMdError, OSError):
                return []
            found = []
            for value in system.colors.values():
                parsed = parse(str(system.resolve(value)))
                if parsed is not None and parsed[3] == 1.0:
                    found.append("#" + to_hex(parsed).lower())
            return list(dict.fromkeys(found))
    return []


def _project_sources(root: Path) -> list[Path]:
    found = []
    for path in root.rglob("*"):
        if path.suffix not in MARKUP_SUFFIXES | STYLE_SUFFIXES or not path.is_file():
            continue
        if SKIPPED_FOLDERS.intersection(path.relative_to(root).parts):
            continue
        if "test" in path.name.lower() or path.stat().st_size > MAX_FILE_BYTES:
            continue
        found.append(path)
    return found


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _token_values(text: str) -> set[str]:
    return {_normal_colour(value) for value in TOKEN_DEFINITION.findall(text)}


def _is_token_file(text: str) -> bool:
    return bool(DEFINES_TOKENS.search(text))


def token_lint_problems(root: Path) -> list[str]:
    """Findings for the model, one line per kind of drift; empty when the project has no tokens or is clean."""
    texts = {path: _read(path) for path in _project_sources(root)}
    token_files = {
        path for path, text in texts.items() if path.suffix in STYLE_SUFFIXES and _is_token_file(text)
    }
    design_colours = _design_md_colours(root)
    if not token_files:
        if design_colours:
            return [
                "Tokens: DESIGN.md defines colours but the code has no theme tokens. Run design_md_export (css-tailwind) "
                "and import the file once in the main stylesheet, then use its variables."
            ]
        return []
    token_text = "\n".join(texts[path] for path in token_files)
    allowed_colours = _token_values(token_text)
    has_colour_tokens = bool(DEFINES_COLOUR_TOKENS.search(token_text))
    token_fonts = {
        family.strip().strip("\"'").lower()
        for value in re.findall(r"--[\w-]*font[\w-]*\s*:\s*([^;]+);", token_text)
        for family in value.split(",")
    }

    colour_files: list[tuple[str, int]] = []
    font_files: list[tuple[str, str]] = []
    palette_files: list[str] = []
    for path, text in texts.items():
        name = path.relative_to(root).as_posix()
        if path not in token_files:
            literals = {
                _normal_colour(m)
                for m in COLOUR_LITERAL.findall(VAR_WITH_FALLBACK.sub("", text))
                if not _is_neutral(m.lower())
            } - allowed_colours
            if len(literals) >= MIN_DISTINCT_COLOURS:
                colour_files.append((name, len(literals)))
            for match in FONT_DECLARATION.finditer(text):
                value = match.group(1) or match.group(2) or ""
                if "var(" in value:
                    continue
                families = [f.strip().strip("\"'").lower() for f in value.split(",") if f.strip()]
                named = [f for f in families if f not in GENERIC_FONT_KEYWORDS]
                if named and not set(named) & token_fonts:
                    font_files.append((name, named[0]))
                    break
        if has_colour_tokens and DEFAULT_PALETTE_CLASS.search(text):
            palette_files.append(name)

    def where(names: list[str]) -> str:
        return ", ".join(names[:FILES_SHOWN]) + (", ..." if len(names) > FILES_SHOWN else "")

    problems = []
    if design_colours:
        in_code = {_normal_colour(c) for c in design_colours} & allowed_colours
        if len(in_code) * 2 < len(design_colours):
            problems.append(
                f"Tokens: only {len(in_code)} of the {len(design_colours)} colours in DESIGN.md are theme tokens in the code. "
                "Run design_md_export so the code and DESIGN.md agree (change DESIGN.md first when the design changes)."
            )
    if colour_files:
        problems.append(
            f"Tokens: {len(colour_files)} file(s) hard-code three or more colours that are not design tokens "
            f"({where([f'{n} ({c})' for n, c in colour_files])}). Use the theme variables so DESIGN.md and the code agree."
        )
    if font_files:
        problems.append(
            f"Tokens: font families outside the theme ({where([f'{n}: {f}' for n, f in font_files])}). "
            "Define the family once as a theme token and use that."
        )
    if palette_files:
        problems.append(
            f"Tokens: Tailwind's default palette classes (for example bg-blue-500) in {where(palette_files)} although "
            "the project defines its own colours; use the semantic colour tokens."
        )
    return problems
