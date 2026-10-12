"""Asset catalogue (TODO L0): design and coding assets as small files with front-matter, a generated catalogue the
model can search, and the licence ledger. An asset lives in `<skill folder>/assets/<type>/<id>.md`:

    ---
    id: dir-soft-editorial
    type: direction
    title: Soft editorial
    summary: one line saying what it is and when to use it
    moods: [warm, calm]
    products: [charity, health]
    density: airy
    dependencies: []                   # packages to install (npm or pip names)
    files: [{from: recipes/motion.css, to: src/motion.css}]   # copied into the project by add_asset
    licence: original
    source: authored for DebCraft
    tested: how it was verified
    ---
    The usage note and, for text assets, the content itself.

`build_catalogue` validates every asset and writes `catalogue.json`, `INDEX.md` and `LICENSES.md` next to them, so
the model searches a small file instead of hundreds of assets, and a missing licence fails the build."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

ASSET_TYPES = (
    "direction",
    "effect",
    "component",
    "template",
    "section",
    "font-pairing",
    "palette",
    "css-technique",
    "recipe",
    "skeleton",
)
# Visual assets get a preview image; code skeletons and recipes do not need one.
PREVIEW_TYPES = ("direction", "effect", "component", "template", "section", "font-pairing", "palette")
DENSITIES = ("airy", "balanced", "dense", "any")
FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
STOP_WORDS = {
    "a",
    "an",
    "the",
    "for",
    "and",
    "or",
    "of",
    "to",
    "in",
    "with",
    "on",
    "is",
    "it",
    "my",
    "page",
    "site",
}
ASSETS_FOLDER = "assets"
CATALOGUE_FILE = "catalogue.json"
SEARCH_RESULTS = 5


@dataclass
class Asset:
    id: str
    type: str
    title: str
    summary: str
    moods: list[str] = field(default_factory=list)
    products: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    density: str = "any"
    dependencies: list[str] = field(default_factory=list)
    files: list[dict[str, str]] = field(default_factory=list)
    licence: str = ""
    source: str = ""
    tested: str = ""
    preview: str | None = None
    path: str = ""  # relative to the skill folder
    size: int = 0  # characters of the note plus the files it copies

    def to_json(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class BuildResult:
    assets: list[Asset]
    errors: list[str]
    warnings: list[str]


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return [str(item) for item in value]


def parse_asset(path: Path, skill_folder: Path) -> tuple[Asset | None, str, list[str]]:
    """Returns (asset, body, errors); the asset is None when the front-matter cannot be read."""
    relative = path.relative_to(skill_folder).as_posix()
    text = path.read_text(encoding="utf-8")
    match = FRONT.match(text)
    if match is None:
        return None, "", [f"{relative}: no front-matter block"]
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as error:
        return None, "", [f"{relative}: front-matter is not valid YAML ({error})"]
    if not isinstance(meta, dict):
        return None, "", [f"{relative}: front-matter must be a mapping"]
    body = text[match.end() :].strip()
    files = [
        {"from": str(item.get("from", "")), "to": str(item.get("to", ""))}
        for item in (meta.get("files") or [])
        if isinstance(item, dict)
    ]
    asset = Asset(
        id=str(meta.get("id", "")),
        type=str(meta.get("type", "")),
        title=str(meta.get("title", "")),
        summary=str(meta.get("summary", "")),
        moods=_as_list(meta.get("moods")),
        products=_as_list(meta.get("products")),
        tags=_as_list(meta.get("tags")),
        density=str(meta.get("density", "any")),
        dependencies=_as_list(meta.get("dependencies")),
        files=files,
        licence=str(meta.get("licence", "")).strip(),
        source=str(meta.get("source", "")).strip(),
        tested=str(meta.get("tested", "")).strip(),
        preview=str(meta["preview"]) if meta.get("preview") else None,
        path=relative,
    )
    return asset, body, []


def validate_asset(asset: Asset, skill_folder: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    where = asset.path
    if not SLUG.match(asset.id):
        errors.append(f"{where}: id {asset.id!r} must be lowercase letters, digits and hyphens")
    if asset.type not in ASSET_TYPES:
        errors.append(f"{where}: type {asset.type!r} is not one of {', '.join(ASSET_TYPES)}")
    elif Path(where).parent.name != asset.type:
        errors.append(f"{where}: lives in the wrong folder for type {asset.type!r}")
    if Path(where).stem != asset.id:
        errors.append(f"{where}: file name must be the id ({asset.id}.md)")
    for name in ("title", "summary", "licence", "source", "tested"):
        if not getattr(asset, name):
            errors.append(f"{where}: missing {name}")
    if asset.density not in DENSITIES:
        errors.append(f"{where}: density {asset.density!r} must be one of {', '.join(DENSITIES)}")
    for item in asset.files:
        if not item["from"] or not item["to"]:
            errors.append(f"{where}: every file needs `from` and `to`")
        elif not (skill_folder / item["from"]).is_file():
            errors.append(f"{where}: file {item['from']} does not exist")
        elif ".." in Path(item["to"]).parts or Path(item["to"]).is_absolute():
            errors.append(f"{where}: target {item['to']} must be a relative path inside the project")
    if asset.preview is None and asset.type in PREVIEW_TYPES:
        warnings.append(f"{where}: no preview image yet")
    elif asset.preview is not None and not (skill_folder / asset.preview).is_file():
        errors.append(f"{where}: preview {asset.preview} does not exist")
    return errors, warnings


def build_catalogue(skill_folder: Path) -> BuildResult:
    """Reads every asset under `<skill folder>/assets`, validates them and returns the entries (not written yet)."""
    assets: list[Asset] = []
    errors: list[str] = []
    warnings: list[str] = []
    seen: dict[str, str] = {}
    root = skill_folder / ASSETS_FOLDER
    for path in sorted(root.glob("*/*.md")) if root.is_dir() else []:
        if path.name == "INDEX.md":
            continue
        asset, body, problems = parse_asset(path, skill_folder)
        errors.extend(problems)
        if asset is None:
            continue
        found, soft = validate_asset(asset, skill_folder)
        errors.extend(found)
        warnings.extend(soft)
        if asset.id in seen:
            errors.append(f"{asset.path}: id {asset.id} is already used by {seen[asset.id]}")
        seen[asset.id] = asset.path
        copied = sum(
            len((skill_folder / item["from"]).read_text(encoding="utf-8", errors="replace"))
            for item in asset.files
            if (skill_folder / item["from"]).is_file()
        )
        asset.size = len(body) + copied
        assets.append(asset)
    return BuildResult(assets, errors, warnings)


def index_markdown(assets: list[Asset]) -> str:
    lines = ["# Asset index", "", "Generated by `scripts/build_asset_catalogue.py`; do not edit by hand.", ""]
    for asset_type in ASSET_TYPES:
        group = [a for a in assets if a.type == asset_type]
        if not group:
            continue
        lines += [f"## {asset_type} ({len(group)})", ""]
        for asset in group:
            moods = f" [{', '.join(asset.moods)}]" if asset.moods else ""
            lines.append(f"- `{asset.id}`: {asset.title}. {asset.summary}{moods}")
        lines.append("")
    return "\n".join(lines)


def licences_markdown(assets: list[Asset]) -> str:
    lines = [
        "# Asset licences",
        "",
        "Generated from the assets' front-matter; do not edit by hand.",
        "",
        "| Asset | Licence | Source |",
        "|---|---|---|",
    ]
    lines += [f"| `{a.id}` | {a.licence} | {a.source} |" for a in assets]
    return "\n".join(lines) + "\n"


def catalogue_files(result: BuildResult) -> dict[str, str]:
    """The generated files by name, ready to write or to compare with what is committed."""
    payload = {"version": 1, "assets": [a.to_json() for a in result.assets]}
    return {
        CATALOGUE_FILE: json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
        "INDEX.md": index_markdown(result.assets),
        "LICENSES.md": licences_markdown(result.assets),
    }


def write_catalogue(skill_folder: Path) -> BuildResult:
    result = build_catalogue(skill_folder)
    if not result.errors:
        for name, text in catalogue_files(result).items():
            (skill_folder / ASSETS_FOLDER / name).write_text(text, encoding="utf-8", newline="\n")
    return result


def load_catalogue(skill_folder: Path) -> list[Asset]:
    path = skill_folder / ASSETS_FOLDER / CATALOGUE_FILE
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Asset(**item) for item in data.get("assets", [])]


def _tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP_WORDS]


def search(
    assets: list[Asset], query: str, asset_type: str | None = None, limit: int = SEARCH_RESULTS
) -> list[Asset]:
    """Deterministic keyword search; no model call. Id and title words count most, then moods, products and tags,
    then the summary. Ties keep the catalogue order."""
    words = _tokens(query)
    scored: list[tuple[int, int, Asset]] = []
    for position, asset in enumerate(assets):
        if asset_type and asset.type != asset_type:
            continue
        strong = set(_tokens(asset.id.replace("-", " ") + " " + asset.title))
        medium = set(_tokens(" ".join(asset.moods + asset.products + asset.tags)))
        weak = set(_tokens(asset.summary))
        score = sum(3 * (w in strong) + 2 * (w in medium) + (w in weak) for w in words)
        if score > 0 or not words:
            scored.append((score, -position, asset))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [asset for _, _, asset in scored[:limit]]


def describe(asset: Asset) -> str:
    extras = []
    if asset.moods:
        extras.append("moods: " + ", ".join(asset.moods))
    if asset.products:
        extras.append("for: " + ", ".join(asset.products))
    if asset.dependencies:
        extras.append("needs: " + ", ".join(asset.dependencies))
    extras.append(f"{asset.size:,} chars" + (f", copies {len(asset.files)} file(s)" if asset.files else ""))
    return f"- {asset.id} ({asset.type}): {asset.title}. {asset.summary} [{'; '.join(extras)}]"
