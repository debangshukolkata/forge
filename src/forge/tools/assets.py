"""find_asset and add_asset (TODO L0): search the catalogue of design (and later coding) assets that ship with the
skills, and copy the chosen one into the project. The model searches a small catalogue instead of guessing from
memory; adding goes through the write jail like any file write and records the licence in NOTICES.md."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field

from forge.parity.assets import ASSET_TYPES, Asset, describe, load_catalogue, search
from forge.parity.skills import Skill, discover
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.files import _save
from forge.tools.parity import skill_roots

NOTICES_FILE = "NOTICES.md"
UI_SUFFIXES = (".css", ".tsx", ".jsx", ".ts", ".js", ".html", ".vue", ".svelte")
MAX_NOTE_CHARS = 6000


def _catalogues(context: ToolContext) -> list[tuple[Skill, Asset]]:
    found: list[tuple[Skill, Asset]] = []
    for skill in discover(*skill_roots(context)).values():
        found.extend((skill, asset) for asset in load_catalogue(skill.folder))
    return found


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
        lines = [describe(asset) for asset in matches]
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
            description="folder of the front-end project relative to the repository root (empty for the root)",
        )
        overwrite: bool = Field(default=False, description="replace files that already exist and differ")

    def summary(self, args: AddAsset.Args) -> str:
        return f"add asset {args.id}"

    async def run(self, args: AddAsset.Args, context: ToolContext) -> ToolResult:
        entry = next(((s, a) for s, a in _catalogues(context) if a.id == args.id.strip()), None)
        if entry is None:
            return ToolResult(ok=False, content=f"No asset {args.id!r}. Search with find_asset.")
        skill, asset = entry
        base = args.project_dir.strip().strip("/\\")
        written: list[str] = []
        skipped: list[str] = []
        for item in asset.files:
            relative = f"{base}/{item['to']}" if base else item["to"]
            source = _inside(skill.folder, item["from"])
            if source is None:
                return ToolResult(
                    ok=False, content=f"Asset {asset.id} points outside its skill folder; not copied."
                )
            text = source.read_text(encoding="utf-8")
            target = context.workspace.path_of(relative)
            if target.is_file():
                current = target.read_text(encoding="utf-8", errors="replace")
                if current.replace("\r\n", "\n") == text.replace("\r\n", "\n"):
                    skipped.append(f"{relative} (already the same)")
                    continue
                if not args.overwrite:
                    skipped.append(f"{relative} (exists and differs; pass overwrite=true to replace)")
                    continue
            result = await _save(context, relative, text, f"asset {asset.id}", "write")
            if not result.ok:
                return result
            written.append(relative)
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
        parts.append("Usage note:\n" + note)
        return ToolResult(ok=True, content="\n".join(parts), meta={"ui_files": ui_files})


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
