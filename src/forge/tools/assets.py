"""find_asset and add_asset (TODO L0): search the catalogue of design (and later coding) assets that ship with the
skills, and copy the chosen one into the project. The model searches a small catalogue instead of guessing from
memory; adding goes through the write jail like any file write and records the licence in NOTICES.md."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import Field

from forge.parity.assets import ASSET_TYPES, Asset, describe, load_catalogue, search, search_scored
from forge.parity.skills import Skill, discover
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.files import _save
from forge.tools.parity import skill_roots

NOTICES_FILE = "NOTICES.md"
UI_SUFFIXES = (".css", ".tsx", ".jsx", ".ts", ".js", ".html", ".vue", ".svelte")
MAX_NOTE_CHARS = 6000
BINARY_SUFFIXES = {
    ".woff2",
    ".woff",
    ".ttf",
    ".otf",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".ico",
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
}


def _catalogues(context: ToolContext) -> list[tuple[Skill, Asset]]:
    found: list[tuple[Skill, Asset]] = []
    for skill in discover(*skill_roots(context)).values():
        found.extend((skill, asset) for asset in load_catalogue(skill.folder))
    return found


HINT_MIN_SCORE = (
    6  # measured on 12 design requests (all 6 to 17) and 8 others (2 to 4, one form-related request 11)
)
HINT_RESULTS = 3
REFERENCE_SHOTS = frozenset(
    {"desktop", "mobile", "phone", "specimen"}
)  # the picture names build_reference_shots.py and the specimen script make
HINT_MIN_FOLLOWER = 5
HINT_REQUEST_CHARS = 300  # a long message matches everything a little; its start says what is wanted
# Visual assets are hinted only for a request that is about what people see (RH1, D-528): measured on 15 back-end requests, 10 got screens or
# sections ("write a migration that adds a status column" named the bulk-list screen) because words such as form, table and log match their tags.
VISUAL_TYPES = frozenset(
    {
        "direction",
        "effect",
        "component",
        "design-system",
        "section",
        "font",
        "font-pairing",
        "palette",
        "css-technique",
    }
)
UI_REQUEST = re.compile(
    r"\b(pages?|screens?|ui|ux|looks?|looking|design\w*|layouts?|styl\w*|css|themes?|colou?rs?|palettes?|fonts?|typography|sections?|hero|"
    r"landing|website|site|front[- ]?end|animat\w*|motion|effects?|scroll\w*|hover|buttons?|toggles?|accordion|modal|dialog|menu|nav\w*|sidebar|"
    r"cards?|grid|bento|dashboards?|charts?|icons?|logo|poster|portfolio|inputs?|labels?|focus\w*|sortable|searchable|responsive|mobile|"
    r"dark mode|visual\w*|views?|tabs|widgets?|components?|display)\b",
    re.IGNORECASE,
)
DOCUMENT_REQUEST = re.compile(r"\b(word|documents?|docx|memo|proposal|letter|handout)\b", re.IGNORECASE)


def _hint_pool(assets: list[Asset], request: str) -> list[Asset]:
    """The assets a request may be hinted: visual ones (and web page templates) only for a request about what people see, Word templates only
    for a request that names a document; recipes and skeletons always."""
    visual = bool(UI_REQUEST.search(request))
    document = bool(DOCUMENT_REQUEST.search(request))
    pool = []
    for asset in assets:
        tags = {tag.lower() for tag in asset.tags}
        if asset.type in VISUAL_TYPES or (asset.type == "template" and "page" in tags):
            if visual:
                pool.append(asset)
        elif asset.type == "template" and "word" in tags:
            if document:
                pool.append(asset)
        else:
            pool.append(asset)
    return pool


def catalogue_hint(context: ToolContext, request: str) -> str:
    """A note naming the catalogue assets that match a user's request well, or "" when none does (D-518).

    A plain keyword search of the catalogue (no model call, nothing leaves the machine). The model rarely thinks of looking in the catalogue by itself
    (1 run in 24, measured live), so the best matches are put in front of it with each request; it can use one or ignore them."""
    entries = _catalogues(context)
    if not entries:
        return ""
    start = request[:HINT_REQUEST_CHARS]
    found = search_scored(_hint_pool([asset for _, asset in entries], start), start, None, HINT_RESULTS)
    if not found or found[0][0] < HINT_MIN_SCORE:
        return ""
    # The best match has cleared the bar; the next ones are shown when they are nearly as good (at least 5 and half of the best), so a request that fits
    # a recipe and a skeleton (logging) shows both, while a weak tail of loosely related assets stays out.
    top_score = found[0][0]
    matches = [asset for score, asset in found if score >= max(HINT_MIN_FOLLOWER, top_score / 2)]
    return (
        "Catalogue matches for this request, from a keyword search of the tested, ready-to-copy assets. If the first one fits what was asked, call add_asset(id) "
        "on it as your first building step, before you write that part from scratch: it brings the files, the licence note and a usage note you then adapt. "
        "For a colour palette or a design system, add it and take the colours and tokens from what it returns. Research or a question first is fine; "
        "skip the matches only when the request is about something else. find_asset searches for more.\n"
        + "\n".join(describe(asset) for asset in matches)
    )


class FindAsset(Tool):
    name = "find_asset"
    read_only = True
    description = (
        "Search the catalogue of ready-made, tested assets (visual directions, animation effects, accessible "
        "components, later templates, sections, fonts and coding recipes). Give the product and the feeling in a few "
        "words, e.g. 'warm charity landing page' or 'dark dashboard table'. Returns the best matches with their ids; "
        "use add_asset to bring one into the project. Look here before building a design element from memory."
    )

    class Args(ToolArgs):
        query: str = Field(description="what you need, in a few words (product, mood, element)")
        type: str | None = Field(default=None, description=f"optional filter: {', '.join(ASSET_TYPES)}")
        limit: int = Field(default=5, ge=1, le=10)

    async def run(self, args: FindAsset.Args, context: ToolContext) -> ToolResult:
        if args.type and args.type not in ASSET_TYPES:
            return ToolResult(
                ok=False, content=f"Unknown type {args.type!r}. Types: {', '.join(ASSET_TYPES)}."
            )
        entries = _catalogues(context)
        if not entries:
            return ToolResult(
                ok=True, content="No asset catalogue is installed; build from the skill's recipes."
            )
        matches = search([asset for _, asset in entries], args.query, args.type, args.limit)
        if not matches:
            kinds = ", ".join(sorted({asset.type for _, asset in entries}))
            return ToolResult(
                ok=True,
                content=f"Nothing matched {args.query!r}. Try fewer or different words, or filter by type ({kinds}).",
            )
        previews = {skill_asset.id: skill for skill, skill_asset in entries}
        lines = [
            describe(asset)
            + (
                " [reference pictures: add_asset copies them for view_image]"
                if _previews(previews[asset.id].folder, asset.id)
                else ""
            )
            for asset in matches
        ]
        return ToolResult(
            ok=True,
            content="Best matches:\n" + "\n".join(lines) + "\nadd_asset(id) copies one into the project.",
        )


class AddAsset(Tool):
    name = "add_asset"
    description = (
        "Bring a catalogue asset into the project: copies the files it ships (CSS, components) into the project "
        "folder, records its licence in NOTICES.md and returns its usage note, which you then adapt to this product. "
        "Assets without files (visual directions) return their text to follow. Find ids with find_asset."
    )

    class Args(ToolArgs):
        id: str = Field(description="the asset id from find_asset, e.g. fx-count-up")
        project_dir: str = Field(
            default="",
            description="folder of the project relative to the repository root (empty for the root)",
        )
        overwrite: bool = Field(default=False, description="replace files that already exist and differ")
        variables: dict[str, str] = Field(
            default_factory=dict,
            description='values for {{placeholders}} in the asset files and paths, e.g. {"package": "inventory"}',
        )

    def summary(self, args: AddAsset.Args) -> str:
        return f"add asset {args.id}"

    async def run(self, args: AddAsset.Args, context: ToolContext) -> ToolResult:
        entry = next(((s, a) for s, a in _catalogues(context) if a.id == args.id.strip()), None)
        if entry is None:
            return ToolResult(ok=False, content=f"No asset {args.id!r}. Search with find_asset.")
        skill, asset = entry
        base = args.project_dir.strip().strip("/\\")
        missing = sorted(_placeholders(skill.folder, asset) - set(args.variables))
        if missing:
            return ToolResult(
                ok=False,
                content=f"Asset {asset.id} needs values for: {', '.join(missing)}. Pass them in `variables`.",
            )
        written: list[str] = []
        skipped: list[str] = []
        for item in asset.files:
            target_path = _fill(item["to"], args.variables)
            relative = f"{base}/{target_path}" if base else target_path
            source = _inside(skill.folder, item["from"])
            if source is None:
                return ToolResult(
                    ok=False, content=f"Asset {asset.id} points outside its skill folder; not copied."
                )
            binary = source.suffix.lower() in BINARY_SUFFIXES
            data = (
                source.read_bytes() if binary else _fill(source.read_text(encoding="utf-8"), args.variables)
            )
            target = context.workspace.path_of(relative)
            if target.is_file():
                if isinstance(data, bytes):
                    same = target.read_bytes() == data
                else:
                    current = target.read_text(encoding="utf-8", errors="replace")
                    same = current.replace("\r\n", "\n") == data.replace("\r\n", "\n")
                if same:
                    skipped.append(f"{relative} (already the same)")
                    continue
                if not args.overwrite:
                    skipped.append(f"{relative} (exists and differs; pass overwrite=true to replace)")
                    continue
            if isinstance(data, bytes):
                await _save_binary(context, relative, data, f"asset {asset.id}")
            else:
                result = await _save(context, relative, data, f"asset {asset.id}", "write")
                if not result.ok:
                    return result
            written.append(relative)
        context.assets_added.add(asset.id)
        if written:
            _record_licence(context, base, asset)
        ui_files = any(path.lower().endswith(UI_SUFFIXES) for path in written)
        note = _body(skill, asset)
        parts = [f"Added {asset.id} ({asset.title})."]
        if written:
            parts.append("Files written: " + ", ".join(written) + ".")
        if skipped:
            parts.append("Not written: " + "; ".join(skipped) + ".")
        if asset.dependencies:
            parts.append(
                "Install first if missing: " + ", ".join(asset.dependencies) + " (npm install / pip install)."
            )
        shown = await _copy_previews(context, skill, asset)
        if shown:
            parts.append(
                "Reference pictures (what it looks like; open them with view_image and match the feel, do not copy the texts): "
                + ", ".join(shown)
            )
        parts.append("Usage note:\n" + note)
        return ToolResult(ok=True, content="\n".join(parts), meta={"ui_files": ui_files})


REFERENCE_FOLDER = ".forge/reference"


def _previews(skill_folder: Path, asset_id: str) -> list[Path]:
    """Reference pictures of an asset (a desktop and a phone picture, made by scripts/dev/build_reference_shots.py), if it has them."""
    # Only the shot suffixes: `<id>-*.jpg` alone also matched the picture of a different asset whose id starts with this one (fx-marquee and fx-marquee-vertical).
    return sorted(
        picture
        for picture in (skill_folder / "assets" / "preview").glob(f"{asset_id}-*.jpg")
        if picture.stem[len(asset_id) + 1 :] in REFERENCE_SHOTS
    )


async def _copy_previews(context: ToolContext, skill: Skill, asset: Asset) -> list[str]:
    """Copies the asset's reference pictures into the workspace's `.forge/reference/` so the model can look at them."""
    shown: list[str] = []
    for picture in _previews(skill.folder, asset.id):
        target = context.workspace.root / REFERENCE_FOLDER / picture.name
        context.workspace.jail.check(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(picture.read_bytes())
        shown.append(f"{REFERENCE_FOLDER}/{picture.name}")
    return shown


PLACEHOLDER = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")


def _fill(text: str, variables: dict[str, str]) -> str:
    return PLACEHOLDER.sub(lambda match: variables.get(match.group(1), match.group(0)), text)


def _placeholders(folder: Path, asset: Asset) -> set[str]:
    """Names of the {{placeholders}} in the asset's file paths and contents, so a missing value is reported early."""
    found: set[str] = set()
    for item in asset.files:
        found.update(PLACEHOLDER.findall(item["to"]))
        source = _inside(folder, item["from"])
        if source is not None and source.suffix.lower() not in BINARY_SUFFIXES:
            found.update(PLACEHOLDER.findall(source.read_text(encoding="utf-8")))
    return found


async def _save_binary(context: ToolContext, relative: str, data: bytes, reason: str) -> None:
    """Fonts and images: written through the same gate as text, announced like any other file change."""
    existed = context.workspace.path_of(relative).is_file()
    context.workspace.write_bytes(relative, data, reason=reason)
    context.last_edit_step = context.step
    await context.emit("file_changed", {"path": relative, "op": "write" if existed else "create", "diff": ""})


def _inside(folder: Path, relative: str) -> Path | None:
    path = (folder / relative).resolve()
    return path if path.is_file() and folder.resolve() in path.parents else None


def _body(skill: Skill, asset: Asset) -> str:
    text = (skill.folder / asset.path).read_text(encoding="utf-8")
    body = text.split("\n---", 1)[1].split("\n", 1)[1] if text.startswith("---") else text
    body = body.strip()
    return body if len(body) <= MAX_NOTE_CHARS else body[:MAX_NOTE_CHARS] + "\n[note shortened]"


def _record_licence(context: ToolContext, base: str, asset: Asset) -> None:
    """Appends one line per added asset to NOTICES.md in the project folder (once per asset)."""
    relative = f"{base}/{NOTICES_FILE}" if base else NOTICES_FILE
    path = context.workspace.path_of(relative)
    existing = (
        path.read_text(encoding="utf-8")
        if path.is_file()
        else "# Notices\n\nAssets added from DebCraft's catalogue.\n"
    )
    line = f"- {asset.id} ({asset.title}): {asset.licence}; {asset.source}"
    if line in existing:
        return
    context.workspace.write_text(
        relative, existing.rstrip("\n") + "\n" + line + "\n", reason=f"licence of {asset.id}"
    )
