"""theme_search (TH1..TH5, D-492): find a theme the user likes, study it read-only, and prove the page written afterwards shares no code with it.

Three actions. `search` lists themes from the public lists (WordPress.org, WordPress.com, GitHub) and saves their screenshots so the model can show the user up to
four in one ask_user question. `study` reads a public repository or a WordPress.org theme package into memory (never into the project) and writes facts, a draft
DESIGN.md and a fingerprint under `.forge/inspiration/`. `check` compares the project's own pages with that fingerprint. The rules are in docs/THEME_CLEAN_ROOM.md."""

from __future__ import annotations

import json
import re
from typing import Literal
from urllib.parse import quote

import httpx
from pydantic import Field

from forge.designsystem.extract import Extracted, draft_design_md
from forge.designsystem.lint import describe_findings, lint_text
from forge.errors import ForgeError
from forge.net import connection_hint, root_cause
from forge.slides.rawpackage import check_archive
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools import theme_sources as sources
from forge.tools.image_sources import SourceError
from forge.tools.vision import _relative
from forge.tools.web_guard import WebPolicy

FOLDER = ".forge/inspiration"
PICTURES = ".forge/themes"
SKIPPED = {".forge", "node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv"}
MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"RIFF", b"GIF8")
ROLE_OF = {
    "primary": "primary",
    "secondary": "secondary",
    "accent": "accent",
    "tertiary": "accent",
    "base": "neutral",
    "background": "neutral",
    "contrast": "ink",
    "foreground": "ink",
    "surface": "surface",
    "base-2": "surface",
    "border": "border",
    "muted": "muted",
}


def slug_of(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "theme"


class ThemeSearch(Tool):
    name = "theme_search"
    sends_outside = True
    read_only = False
    description = (
        "Theme inspiration. `search`: find themes by look or name in the public lists (WordPress.org, WordPress.com, GitHub) and save their screenshots, so you can show "
        "up to four to the user with ONE ask_user call. `study`: read a theme read-only (a GitHub repository `owner/name` or address, or a WordPress.org theme name) and write "
        "its facts (colours, fonts, sizes, widths, section order, licence) and a draft DESIGN.md under .forge/inspiration. `check`: after building the page, prove that "
        "it shares no code with the studied theme. Nothing the theme wrote is ever copied: see skill theme-inspiration."
    )

    class Args(ToolArgs):
        action: Literal["search", "study", "check"]
        query: str = Field(
            default="", description="search: the look or the name, for example 'minimal portfolio'"
        )
        source: str = Field(
            default="",
            description="study: a repository as owner/name or address, or a WordPress.org theme name",
        )
        slug: str = Field(default="", description="check: which studied theme (empty = all studied themes)")

    def summary(self, args: ThemeSearch.Args) -> str:
        return f"theme {args.action}: {args.query or args.source or args.slug or 'all'}"

    async def run(self, args: ThemeSearch.Args, context: ToolContext) -> ToolResult:
        try:
            if args.action == "check":
                return self._check(args, context)
            for text in (args.query, args.source):
                if any(re.search(re.escape(t), text, re.IGNORECASE) for t in context.sensitive_terms):
                    return ToolResult(
                        ok=False,
                        content="That text contains a term from this host (Mode B sensitive terms): rephrase without it.",
                    )
            policy = context.web_policy or WebPolicy()
            async with sources.make_client() as client:
                if args.action == "search":
                    return await self._search(args, context, client, policy)
                return await self._study(args, context, client, policy)
        except (ForgeError, SourceError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        except httpx.HTTPError as error:
            detail = root_cause(error)
            return ToolResult(
                ok=False,
                content=f"The theme site could not be reached ({detail[:120]}): {connection_hint(detail, 'api.wordpress.org')}",
            )

    async def _search(
        self, args: ThemeSearch.Args, context: ToolContext, client: httpx.AsyncClient, policy: WebPolicy
    ) -> ToolResult:
        if not args.query.strip():
            return ToolResult(ok=False, content="Give `query`: the look or the theme's name.")
        themes, notes = await sources.search_themes(client, args.query.strip(), policy)
        if not themes:
            return ToolResult(
                ok=False,
                content="No theme found"
                + (f" ({'; '.join(notes)})" if notes else "")
                + ". Ask the user for a theme name, a repository or a demo address; design_inspire reads a demo address.",
            )
        lines: list[str] = []
        for theme in themes[:8]:
            picture = ""
            if theme.screenshot_url and len([line for line in lines if "Picture:" in line]) < 4:
                try:
                    data = await sources.get_bytes(client, theme.screenshot_url, policy, 3_000_000)
                except (SourceError, httpx.HTTPError):
                    data = b""
                if data.startswith(MAGIC):
                    target = f"{PICTURES}/{slug_of(theme.source + '-' + theme.slug)}.png"
                    context.workspace.write_bytes(target, data, "screenshot of a theme the user may like")
                    picture = f" Picture: {_relative(context, context.workspace.path_of(target))}"
            lines.append(f"- {theme.line()}.{picture}")
        return ToolResult(
            ok=True,
            content=(
                f"Themes for '{args.query}':\n"
                + "\n".join(lines)
                + ("\n(Not read: " + "; ".join(notes) + ")" if notes else "")
                + "\n\nNEXT STEP: put up to four of these to the user with ONE ask_user call (label the name, description what it looks like, image the picture), and say they can "
                "ask for more or type another name or link. Then call theme_search study with the one they pick. The pictures are for choosing only."
            ),
        )

    async def _study(
        self, args: ThemeSearch.Args, context: ToolContext, client: httpx.AsyncClient, policy: WebPolicy
    ) -> ToolResult:
        if not args.source.strip():
            return ToolResult(
                ok=False,
                content="Give `source`: owner/name, a repository address or a WordPress.org theme name.",
            )
        repo = sources.github_repo(args.source)
        if repo:
            slug = slug_of(repo.split("/")[1])
            files, where = await self._read_repository(client, policy, repo), f"https://github.com/{repo}"
        else:
            slug = slug_of(sources.theme_slug(args.source))
            try:
                files = await self._read_package(client, policy, slug)
            except SourceError as error:
                listed = await sources.wpcom_theme(client, slug, policy)
                if listed is None:
                    raise error
                demo = str(listed.get("demo_uri") or "")
                return ToolResult(
                    ok=False,
                    content=(
                        f"'{listed.get('name', slug)}' is listed on WordPress.com ({listed.get('theme_type', 'theme')}) but has no public theme files, "
                        "so it cannot be studied by its files. Say so to the user"
                        + (
                            f" and work from its demo with design_inspire: {demo}"
                            if demo
                            else " and ask for a demo address"
                        )
                        + ". We do not copy a paid theme; offer an original page with the same feel."
                    ),
                )
            where = f"https://wordpress.org/themes/{quote(slug)}/"
        if not files:
            return ToolResult(
                ok=False,
                content="No theme files could be read there. Say so to the user and work from the preview address with design_inspire, or ask for another theme.",
            )
        study = sources.study_files(slug, files)
        draft = self._draft(study, where)
        context.workspace.write_text(
            f"{FOLDER}/{slug}.md", self._note(study, where), "facts about a studied theme"
        )
        context.workspace.write_text(
            f"{FOLDER}/{slug}.DESIGN.md", draft, "draft design system from a studied theme"
        )
        context.workspace.write_text(
            f"{FOLDER}/{slug}.fingerprint.json",
            json.dumps({"slug": slug, "windows": sources.WINDOW, "hashes": study.fingerprint}),
            "fingerprint of the studied files (hashes, no text)",
        )
        self._log(context, study, where)
        context.last_edit_step = context.step
        findings = describe_findings([f for f in lint_text(draft) if f.severity in ("error", "warning")], 8)
        return ToolResult(
            ok=True,
            content=(
                f"Studied {where} read-only ({len(files)} files, nothing saved into the project but facts).\n"
                f"Licence: {study.licence or 'not stated in style.css'}"
                + (f" ({study.licence_uri})" if study.licence_uri else "")
                + ".\n"
                f"Palette: {', '.join(f'{k} {v}' for k, v in list(study.palette.items())[:10]) or 'not in theme.json'}.\n"
                f"Fonts: {', '.join(study.fonts) or 'not named'}. Widths: {study.layout or 'not named'}.\n"
                f"Sections read: {len(study.sections)}. Notes: {FOLDER}/{slug}.md; draft design system: {FOLDER}/{slug}.DESIGN.md.\n{findings}\n\n"
                "NEXT STEP: show the user what you learned in ONE ask_user question (palette, fonts, section order) so they can say 'keep the colours, change the layout'. "
                "Then write the page from our own DESIGN.md and compositions, with our own markup, words and drawings, and fonts from find_font. Never copy a line, a text or a picture, and "
                "never put the theme's name or logo in the page. When the page is built, call theme_search check."
            ),
        )

    async def _read_repository(
        self, client: httpx.AsyncClient, policy: WebPolicy, repo: str
    ) -> dict[str, str]:
        tree = await sources.get_json(
            client, f"{sources.GITHUB_API}/repos/{repo}/git/trees/HEAD?recursive=1", policy
        )
        paths = [
            item["path"]
            for item in tree.get("tree", [])
            if isinstance(item, dict) and item.get("type") == "blob" and isinstance(item.get("path"), str)
        ]
        files: dict[str, str] = {}
        for path in sources.wanted_paths(paths):
            try:
                data = await sources.get_bytes(
                    client, f"{sources.GITHUB_RAW}/{repo}/HEAD/{quote(path)}", policy
                )
            except SourceError:
                continue
            files[path] = data.decode("utf-8", errors="replace")
        return files

    async def _read_package(self, client: httpx.AsyncClient, policy: WebPolicy, slug: str) -> dict[str, str]:
        info = await sources.get_json(
            client,
            f"{sources.WPORG_API}?action=theme_information&request[slug]={quote(slug)}&request[fields][download_link]=1",
            policy,
        )
        link = info.get("download_link") if isinstance(info, dict) else ""
        if not isinstance(link, str) or not link.startswith(sources.WPORG_DOWNLOAD):
            raise SourceError(f"WordPress.org has no theme called '{slug}'")
        archive = check_archive(await sources.get_bytes(client, link, policy, 12_000_000))
        names = {
            i.filename: i
            for i in archive.infolist()
            if not i.is_dir() and i.file_size <= sources.MAX_FILE_BYTES
        }
        prefix = next(iter(names)).split("/")[0] + "/" if names else ""
        relative = {name[len(prefix) :]: name for name in names if name.startswith(prefix)}
        files: dict[str, str] = {}
        for path in sources.wanted_paths(list(relative)):
            files[path] = archive.read(relative[path]).decode("utf-8", errors="replace")
        return files

    @staticmethod
    def _draft(study: sources.Study, where: str) -> str:
        found = Extracted()
        for slug, colour in study.palette.items():
            role = ROLE_OF.get(slug.lower())
            if role:
                found.colors.setdefault(role, colour)
        found.fonts = list(study.fonts)
        found.heading_font = study.fonts[0] if study.fonts else ""
        found.notes.append(
            "Drafted from the facts of a studied theme: colours, font names and widths only. The page that follows is written from this file and our own compositions."
        )
        return draft_design_md(found, "Studied theme (draft)", where)

    @staticmethod
    def _note(study: sources.Study, where: str) -> str:
        lines = [
            f"# Studied theme: {study.theme_name or study.slug}",
            "",
            f"- Source: {where} (read-only, public)",
            f"- Licence: {study.licence or 'not stated'} {study.licence_uri}".rstrip(),
            "- Use: facts only, in our own words; no code, text, picture or logo of the theme is used (docs/THEME_CLEAN_ROOM.md).",
            "",
            "## Colours",
            *[f"- {name}: {value}" for name, value in study.palette.items()],
            "",
            "## Type and widths",
            f"- Fonts: {', '.join(study.fonts) or 'not named'}",
            *[f"- Size {name}: {value}" for name, value in study.font_sizes.items()],
            *[f"- {name}: {value}" for name, value in study.layout.items()],
            *[f"- Shadow {value}" for value in study.shadows],
            "",
            "## Section structure (counts only)",
            *[f"- {path}: {structure}" for path, structure in study.sections],
            "",
        ]
        return "\n".join(lines)

    @staticmethod
    def _log(context: ToolContext, study: sources.Study, where: str) -> None:
        log = context.workspace.path_of(f"{FOLDER}/LOG.md")
        before = log.read_text(encoding="utf-8") if log.is_file() else "# Themes studied for this project\n\n"
        line = f"- {study.theme_name or study.slug}: {where}; licence {study.licence or 'not stated'}; facts only.\n"
        if line not in before:
            context.workspace.write_text(f"{FOLDER}/LOG.md", before + line, "one line per theme studied")

    def _check(self, args: ThemeSearch.Args, context: ToolContext) -> ToolResult:
        root = context.workspace.path_of(".")
        prints = sorted((root / FOLDER).glob("*.fingerprint.json")) if (root / FOLDER).is_dir() else []
        if args.slug:
            prints = [p for p in prints if p.name == f"{slug_of(args.slug)}.fingerprint.json"]
        if not prints:
            return ToolResult(
                ok=False, content="No studied theme to compare with: call theme_search study first."
            )
        known: set[int] = set()
        for file in prints:
            known |= set(json.loads(file.read_text(encoding="utf-8")).get("hashes", []))
        results = []
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if (
                not path.is_file()
                or SKIPPED.intersection(relative.parts)
                or path.suffix.lower() not in sources.CHECKED_SUFFIXES
                or path.stat().st_size > 400_000
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            results.append(sources.overlap(known, relative.as_posix(), text))
        close = [r for r in results if r.too_close]
        if close:
            detail = "\n".join(
                f"- {r.path}: {r.shared} of {r.total} runs shared, longest run {r.longest_run}" for r in close
            )
            return ToolResult(
                ok=False,
                content=(
                    "TOO CLOSE to the studied theme: these files contain runs of code that the theme also has.\n"
                    + detail
                    + "\nRewrite those parts from our own design system and compositions (different markup, different class names, own words), then check again. Do not tweak the copied lines."
                ),
            )
        return ToolResult(
            ok=True,
            content=f"Clean: {len(results)} files compared with {len(prints)} studied theme(s); no shared runs of code.",
        )


def theme_search_tools() -> list[Tool]:
    return [ThemeSearch()]
