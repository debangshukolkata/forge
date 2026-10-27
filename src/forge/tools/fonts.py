"""find_font and fetch_font (TODO L3, D-330): any open-licence font on request, and the user's own font when they point to it.

`find_font` searches the Fontsource catalogue (about 2,100 families: Google Fonts and others) by name, look (category) and script
(Hindi, Bengali, Arabic, Korean, ...). `fetch_font` downloads the weights asked for into the project:

- web (woff2): `fonts/<id>/...woff2` and `fonts/<id>.css` with `@font-face` rules and `font-display: swap`, ready to import;
- desktop (ttf): `fonts/<id>/...ttf` and `install-fonts.ps1`, which installs them for the current user without admin rights (the user
  runs it; DebCraft never installs anything outside the project). A deck that uses a font shows it only where the font is installed.
- a font the user names by address (`url`: a .ttf, .otf, .woff2 or a .zip of them): downloaded the same way, licence unchecked.

Every download is kept in DebCraft's library (`<forge home>/library/fonts/<id>/`) so the next project needs no network, and recorded in
NOTICES.md with its licence."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlparse

import httpx
from pydantic import Field

from forge.config import forge_home
from forge.net import connection_hint, root_cause
from forge.slides.rawpackage import check_archive
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools import font_sources as catalogue
from forge.tools.font_sources import FontError
from forge.tools.image_sources import SourceError
from forge.tools.web_guard import WebPolicy, check_resolving

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_FILES = 24
NOTICES = "NOTICES.md"
SITE = "the site's address"  # what a connection hint tells the user to check
MAGIC = {
    "woff2": (b"wOF2",),
    "woff": (b"wOFF",),
    "ttf": (b"\x00\x01\x00\x00", b"true", b"OTTO", b"ttcf"),
}
FONT_SUFFIXES = (".ttf", ".otf", ".woff2", ".woff")
INSTALL_SCRIPT = """# Installs the fonts in this folder for the current Windows user (no administrator rights needed; Windows 10 version 1809 or newer).
# Right-click this file > Run with PowerShell, then restart PowerPoint or the browser.
$destination = Join-Path $env:LOCALAPPDATA 'Microsoft\\Windows\\Fonts'
New-Item -ItemType Directory -Force -Path $destination | Out-Null
$registry = 'HKCU:\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Fonts'
Get-ChildItem -Path $PSScriptRoot -Include *.ttf, *.otf -Recurse | ForEach-Object {
    $target = Join-Path $destination $_.Name
    Copy-Item -Path $_.FullName -Destination $target -Force
    New-ItemProperty -Path $registry -Name ($_.BaseName + ' (TrueType)') -Value $target -PropertyType String -Force | Out-Null
    Write-Host ('Installed ' + $_.Name)
}
"""


def library_folder() -> Path:
    return forge_home() / "library" / "fonts"


def font_id(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")


class FindFont(Tool):
    name = "find_font"
    sends_outside = True
    read_only = True
    description = (
        "Search open-licence fonts (about 2,100 families from Google Fonts and others: OFL, Apache, MIT) by name, look and script. "
        "Use a name ('Inter', 'Playfair'), a look (category: sans-serif, serif, monospace, display, handwriting) and/or a script "
        "('hindi', 'bengali', 'arabic', 'korean', 'cyrillic'). Returns ids for fetch_font. 14 families ship with DebCraft for web "
        "pages (marked); everything else is downloaded by fetch_font on request. Fonts that are not open (Helvetica, Gotham, "
        "company fonts) cannot be found here: the user provides the file or an address for fetch_font."
    )

    class Args(ToolArgs):
        query: str = Field(default="", max_length=100, description="A font name or words describing it")
        category: Literal["", "sans-serif", "serif", "monospace", "display", "handwriting"] = ""
        script: str = Field(
            default="", max_length=30, description="A script or language: bengali, devanagari, arabic, ..."
        )
        limit: int = Field(default=10, ge=1, le=30)

    def summary(self, args: FindFont.Args) -> str:
        return f"find font: {args.query or args.script or args.category}"

    async def run(self, args: FindFont.Args, context: ToolContext) -> ToolResult:
        fonts, origin = await catalogue.load_catalogue()
        found = catalogue.search(fonts, args.query, args.category, args.script, args.limit)
        kept = sorted(p.name for p in library_folder().iterdir()) if library_folder().is_dir() else []
        if not found:
            return ToolResult(
                ok=True,
                content=f"No open-licence font matched. (Catalogue: {origin}.) Try a different word, drop the category, or ask the user "
                "for the font file or an address.",
            )
        lines = [
            f"{i}. {font.describe()}{' [in the library: no download]' if font.id in kept else ''}"
            for i, font in enumerate(found, 1)
        ]
        return ToolResult(
            ok=True,
            content=f"{len(found)} font(s) (catalogue: {origin}):\n"
            + "\n".join(lines)
            + "\n\nfetch_font with the id; weights 400 and 700 are the usual pair; for another script add it to `scripts` (with latin).",
        )


class FetchFont(Tool):
    name = "fetch_font"
    sends_outside = True
    read_only = False
    description = (
        "Download a font into the project: by `font` (an id from find_font, or a family name) as web files (woff2 plus a ready "
        "@font-face CSS file) and/or desktop files (ttf plus install-fonts.ps1 that installs them for the user without admin rights); or "
        "by `url` for a font the user names (a .ttf, .otf, .woff2 or a .zip of them; licence not checked, say so). The weights default to "
        "400 and 700. Files go to fonts/ in the project and are kept in DebCraft's library for offline reuse. A deck shows a non-standard "
        "font only on computers where it is installed: for decks also tell the user to run install-fonts.ps1, or deliver a PDF."
    )

    class Args(ToolArgs):
        font: str = Field(
            default="", max_length=100, description="An id from find_font, e.g. inter, or a family name"
        )
        url: str = Field(
            default="", description="Instead of `font`: an address the user gave for a font file or a zip"
        )
        weights: list[int] = Field(default_factory=lambda: [400, 700])
        scripts: list[str] = Field(default_factory=lambda: ["latin"], description="e.g. [latin, bengali]")
        italic: bool = False
        formats: list[Literal["woff2", "woff", "ttf"]] = Field(default=["woff2"])
        folder: str = Field(default="fonts", description="Where in the project the files go")

    def summary(self, args: FetchFont.Args) -> str:
        return f"fetch font: {args.font or args.url}"

    async def run(self, args: FetchFont.Args, context: ToolContext) -> ToolResult:
        if bool(args.font) == bool(args.url):
            return ToolResult(
                ok=False, content="Give either `font` (a name or id) or `url`, not both and not neither."
            )
        folder = args.folder.strip().strip("/") or "fonts"
        try:
            if args.url:
                return await self._from_url(args, context, folder)
            return await self._from_catalogue(args, context, folder)
        except (FontError, SourceError) as error:
            return ToolResult(ok=False, content=str(error))
        except httpx.HTTPError as error:
            detail = root_cause(error)
            return ToolResult(
                ok=False,
                content=f"The font could not be downloaded ({detail[:120]}): {connection_hint(detail, SITE)}",
            )

    async def _from_catalogue(self, args: FetchFont.Args, context: ToolContext, folder: str) -> ToolResult:
        wanted = font_id(args.font)
        policy = context.web_policy or WebPolicy()
        async with catalogue.make_client() as client:
            fonts, _ = await catalogue.load_catalogue(client)
            match = next((f for f in fonts if f.id == wanted), None) or next(
                iter(catalogue.search(fonts, args.font, limit=1)), None
            )
            if match is None:
                return ToolResult(
                    ok=False,
                    content=f"No open-licence font called '{args.font}': use find_font, or ask the user for the file.",
                )
            missing = [s for s in args.scripts if s not in match.subsets]
            if missing:
                return ToolResult(
                    ok=False,
                    content=f"{match.family} has no {', '.join(missing)} script. It has: {', '.join(match.subsets)}.",
                )
            if args.italic and "italic" not in match.styles:
                return ToolResult(ok=False, content=f"{match.family} has no italic.")
            usable = [w for w in args.weights if w in match.weights]
            if not usable:
                return ToolResult(
                    ok=False,
                    content=f"{match.family} has the weights {', '.join(map(str, match.weights))}; none of {args.weights} exist.",
                )
            style_name = "italic" if args.italic else "normal"
            wanted_files = [
                (fmt, s, w, style_name) for fmt in args.formats for w in usable for s in args.scripts
            ]
            if all(
                (library_folder() / match.id / f"{s}-{w}-{st}.{fmt}").is_file()
                for fmt, s, w, st in wanted_files
            ):
                plan = [
                    (fmt, s, w, st, "") for fmt, s, w, st in wanted_files
                ]  # all in the library: no network needed
            else:
                meta = await catalogue.metadata(match.id, client)
                plan = []
                for fmt in args.formats:
                    plan += [
                        (fmt, *v)
                        for v in catalogue.variant_urls(meta, usable, args.scripts, args.italic, fmt)
                    ]
            if not plan:
                return ToolResult(
                    ok=False,
                    content=f"{match.family} has no {'/'.join(args.formats)} files for that weight and script.",
                )
            if len(plan) > MAX_FILES:
                return ToolResult(
                    ok=False,
                    content=f"{len(plan)} files is too many in one go (limit {MAX_FILES}): ask for fewer weights or scripts.",
                )
            written: list[tuple[str, int, str, str]] = []
            from_library = 0
            for fmt, script, weight, style_name, url in plan:
                name = f"{script}-{weight}-{style_name}.{fmt}"
                kept = library_folder() / match.id / name
                if kept.is_file():
                    data, from_library = kept.read_bytes(), from_library + 1
                else:
                    data = await _fetch_bytes(client, url, policy)
                    _check_magic(data, fmt, name)
                    kept.parent.mkdir(parents=True, exist_ok=True)
                    kept.write_bytes(data)
                context.workspace.write_bytes(f"{folder}/{match.id}/{name}", data, f"font {match.family}")
                written.append((script, weight, style_name, name))
        return self._report(
            context, match.family, match.id, match.licence, folder, args.formats, written, from_library
        )

    def _report(
        self,
        context: ToolContext,
        family: str,
        fid: str,
        licence: str,
        folder: str,
        formats: Sequence[str],
        written: list[tuple[str, int, str, str]],
        from_library: int,
    ) -> ToolResult:
        lines = [
            f"Saved {len(written)} file(s) of {family} ({licence}) in {folder}/{fid}/"
            + (f" ({from_library} from DebCraft's library, no download)" if from_library else "")
            + "."
        ]
        web = _all_web_files(context, folder, fid) or [w for w in written if w[3].endswith(".woff2")]
        if web:
            css = catalogue.font_face_css(family, web, f"./{fid}")
            context.workspace.write_text(f"{folder}/{fid}.css", css, f"@font-face rules for {family}")
            lines.append(
                f"Web: import `{folder}/{fid}.css` (in CSS: @import './{fid}.css' from the fonts folder, or link it) and use font-family: '{family}', system-ui, sans-serif."
            )
        if any(w[3].endswith((".ttf", ".otf")) for w in written):
            context.workspace.write_text(
                f"{folder}/{fid}/install-fonts.ps1", INSTALL_SCRIPT, "installs the fonts for the current user"
            )
            lines.append(
                f"Desktop: tell the user to run {folder}/{fid}/install-fonts.ps1 (right-click, Run with PowerShell; per user, no admin) and restart "
                f"PowerPoint, then use the family name '{family}' in decks. Anyone who opens the deck needs the font installed too, or send a PDF."
            )
        _notice(
            context,
            f"{family} ({fid}) in `{folder}/{fid}/`: {licence}, from Fontsource / Google Fonts. Fonts licensed under the SIL OFL may be used, embedded and redistributed with the project.",
        )
        return ToolResult(ok=True, content="\n".join(lines))

    async def _from_url(self, args: FetchFont.Args, context: ToolContext, folder: str) -> ToolResult:
        policy = context.web_policy or WebPolicy()
        async with catalogue.make_client() as client:
            data = await _fetch_bytes(client, args.url, policy)
        name = unquote(Path(urlparse(args.url).path).name) or "font"
        files: dict[str, bytes] = {}
        if name.lower().endswith(".zip") or data[:2] == b"PK":
            files = _fonts_in_zip(data)
        elif name.lower().endswith(FONT_SUFFIXES):
            files = {re.sub(r"[^A-Za-z0-9._-]", "_", name): data}
        if not files:
            return ToolResult(
                ok=False,
                content="The address did not give a font file (.ttf, .otf, .woff2, .woff) or a zip that holds one.",
            )
        base = font_id(Path(name).stem) or "custom-font"
        for file_name, content in files.items():
            fmt = (
                "ttf"
                if file_name.lower().endswith((".ttf", ".otf"))
                else file_name.rsplit(".", 1)[-1].lower()
            )
            _check_magic(content, fmt, file_name)
            context.workspace.write_bytes(
                f"{folder}/{base}/{file_name}", content, "font from an address the user gave"
            )
            kept = library_folder() / base / file_name
            kept.parent.mkdir(parents=True, exist_ok=True)
            kept.write_bytes(content)
        desktop = any(n.lower().endswith((".ttf", ".otf")) for n in files)
        if desktop:
            context.workspace.write_text(
                f"{folder}/{base}/install-fonts.ps1",
                INSTALL_SCRIPT,
                "installs the fonts for the current user",
            )
        _notice(
            context,
            f"{base} in `{folder}/{base}/`: from {urlparse(args.url).hostname}; licence NOT checked by DebCraft: confirm you may use it.",
        )
        return ToolResult(
            ok=True,
            content=f"Saved {len(files)} font file(s) in {folder}/{base}/: {', '.join(sorted(files))}. The licence was not checked: tell the user to "
            "confirm they may use this font."
            + (
                f" Desktop use: run {folder}/{base}/install-fonts.ps1 (per user, no admin)."
                if desktop
                else ""
            ),
        )


def _all_web_files(context: ToolContext, folder: str, fid: str) -> list[tuple[str, int, str, str]]:
    """Every woff2 file now in the font's folder (this call's and earlier calls'), so the CSS file always lists all weights."""
    found = []
    place = context.workspace.path_of(f"{folder}/{fid}")
    for path in sorted(place.glob("*.woff2")) if place.is_dir() else []:
        match = re.fullmatch(r"([a-z0-9-]+)-(\d+)-(normal|italic)\.woff2", path.name)
        if match:
            found.append((match.group(1), int(match.group(2)), match.group(3), path.name))
    return found


async def _fetch_bytes(client: httpx.AsyncClient, url: str, policy: WebPolicy) -> bytes:
    from forge.tools.findimage import _download

    reason = await check_resolving(url, policy)
    if reason:
        raise SourceError(f"Not downloaded: {reason}.")
    data, _ = await _download(client, url, policy, MAX_FILE_BYTES)
    return data


def _check_magic(data: bytes, fmt: str, name: str) -> None:
    if not any(data.startswith(m) for m in MAGIC.get(fmt, ())):
        raise FontError(f"{name} is not a {fmt} font file (a proxy or login page may have answered)")


def _fonts_in_zip(data: bytes) -> dict[str, bytes]:
    """The font files of a zip (archive checks first; names flattened and cleaned; at most MAX_FILES)."""
    archive = check_archive(data)
    out: dict[str, bytes] = {}
    for info in archive.infolist():
        name = Path(info.filename).name
        if info.is_dir() or not name.lower().endswith(FONT_SUFFIXES) or info.file_size > MAX_FILE_BYTES:
            continue
        out[re.sub(r"[^A-Za-z0-9._-]", "_", name)] = archive.read(info.filename)
        if len(out) >= MAX_FILES:
            break
    return out


def _notice(context: ToolContext, line: str) -> None:
    try:
        existing, _ = context.workspace.read_text(NOTICES)
    except (OSError, ValueError, KeyError):
        existing = "# Notices\n\nThird-party material used in this project.\n"
    if line not in existing:
        context.workspace.write_text(
            NOTICES, existing.rstrip("\n") + "\n- " + line + "\n", "font recorded in NOTICES.md"
        )


def font_tools() -> list[Tool]:
    return [FindFont(), FetchFont()]
