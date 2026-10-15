"""The design knowledge base (TODO DIE3, D-426): what earlier references taught, and what recent projects already used.

It lives in DebCraft's profile folder (`<forge home>/library/design/`), not in a project, and holds two kinds of record:

- **reference**: a public page that was looked at (`design_inspire`): industry, mood, layout words, the principles worth reusing, the measured tokens, the
  source link and a small picture. Only principles and measurements are kept, never the brand's own text, logo or photographs.
- **use**: the palette, the font pair and the composition a finished design chose, with the date. The names of products and clients are not stored.

`design_kb_search` finds references by industry, mood and layout words and lists the last designs' choices so a new design does not repeat them."""

from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

from pydantic import Field

from forge.config import forge_home
from forge.designsystem.extract import from_computed
from forge.designsystem.novelty import MIN_DIFFERENT_DIMENSIONS, Fingerprint, differences, fingerprint
from forge.designsystem.spec import DesignMdError, parse_design_md
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

MAX_REFERENCES = 400
MAX_USES = 60
RECENT_USES = 5
INSPIRATION = ".forge/inspiration"


def folder() -> Path:
    return forge_home() / "library" / "design"


def _index() -> Path:
    return folder() / "index.json"


def load() -> list[dict[str, Any]]:
    try:
        data = json.loads(_index().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [r for r in data if isinstance(r, dict) and r.get("kind") in ("reference", "use")]


def _save(records: list[dict[str, Any]]) -> None:
    references = [r for r in records if r["kind"] == "reference"][-MAX_REFERENCES:]
    uses = [r for r in records if r["kind"] == "use"][-MAX_USES:]
    keep = {id(r) for r in references + uses}
    for gone in (r for r in records if r["kind"] == "reference" and id(r) not in keep):
        (folder() / gone.get("thumbnail", "?")).unlink(missing_ok=True)
    folder().mkdir(parents=True, exist_ok=True)
    _index().write_text(json.dumps(references + uses, indent=1), encoding="utf-8")


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "reference"


def add_reference(record: dict[str, Any], thumbnail: Path | None = None) -> dict[str, Any]:
    """Adds (or replaces, by id) a reference. `record` has id, title, source, industry, mood, layout, principles, tokens, sections."""
    records = [r for r in load() if not (r["kind"] == "reference" and r.get("id") == record["id"])]
    entry = {**record, "kind": "reference", "added": time.strftime("%Y-%m-%d")}
    if thumbnail is not None and thumbnail.is_file():
        name = f"{_slug(record['id'])}{thumbnail.suffix}"
        folder().mkdir(parents=True, exist_ok=True)
        shutil.copyfile(thumbnail, folder() / name)
        entry["thumbnail"] = name
    records.append(entry)
    _save(records)
    return entry


def search_references(query: str, limit: int = 5) -> list[dict[str, Any]]:
    words = _words(query)
    scored: list[tuple[int, dict[str, Any]]] = []
    for record in load():
        if record["kind"] != "reference":
            continue
        # industry and mood count double: they decide fit, the layout words refine it
        hay = _words(f"{record.get('industry', '')} {record.get('mood', '')}")
        rest = _words(
            f"{record.get('layout', '')} {record.get('title', '')} {' '.join(record.get('principles', []))}"
        )
        score = 2 * len(words & hay) + len(words & rest)
        if score:
            scored.append((score, record))
    scored.sort(key=lambda row: row[1].get("added", ""), reverse=True)  # newest first among equals
    scored.sort(key=lambda row: -row[0])
    return [r for _, r in scored[:limit]]


def recent_uses(count: int = RECENT_USES) -> list[dict[str, Any]]:
    return [r for r in load() if r["kind"] == "use"][-count:]


def use_from_design_md(text: str) -> dict[str, Any] | None:
    """The choices of a DESIGN.md that matter for not repeating them: accent, background, the two font families, the composition."""
    try:
        system = parse_design_md(text)
    except DesignMdError:
        return None
    families: list[str] = []
    for token in system.typography.values():
        family = (
            str(token.get("fontFamily", "")).split(",")[0].strip().strip("'\"")
            if isinstance(token, dict)
            else ""
        )
        if family and family not in families:
            families.append(family)
    colours = system.colors
    if not colours and not families:
        return None
    return {
        "kind": "use",
        "primary": str(colours.get("primary", "")),
        "neutral": str(colours.get("neutral", "")),
        "fonts": families[:2],
        "composition": str(system.extra.get("composition", "")),
        "fingerprint": list(fingerprint(system).values()),
        "added": time.strftime("%Y-%m-%d"),
    }


def record_use(text: str) -> dict[str, Any] | None:
    entry = use_from_design_md(text)
    if entry is None:
        return None
    records = load()
    # the same design recorded again on the same day is one use
    if any(
        r["kind"] == "use"
        and {k: r.get(k) for k in entry if k != "added"} == {k: entry[k] for k in entry if k != "added"}
        for r in records[-RECENT_USES:]
    ):
        return entry
    records.append(entry)
    _save(records)
    return entry


def repeats_recent(text: str, count: int = RECENT_USES) -> list[str]:
    """The recent designs this DESIGN.md resembles: fewer than three of the dimensions where both say something differ (DIE5). Empty when none, or when it cannot be read."""
    mine = use_from_design_md(text)
    if mine is None:
        return []
    found: list[str] = []
    for use in recent_uses(count):
        values = use.get("fingerprint")
        if not isinstance(values, list) or len(values) != len(mine["fingerprint"]):
            continue
        different = differences(Fingerprint(*map(str, mine["fingerprint"])), Fingerprint(*map(str, values)))
        if len(different) < MIN_DIFFERENT_DIMENSIONS:
            found.append(
                f"{use.get('added', '')}: "
                + (f"differs only in {', '.join(different)}" if different else "the same on every dimension")
            )
    return found


def describe_reference(record: dict[str, Any]) -> str:
    tokens = record.get("tokens", {})
    colours = ", ".join(f"{k} {v}" for k, v in tokens.get("colors", {}).items())
    thumbnail = f"; picture {folder() / record['thumbnail']}" if record.get("thumbnail") else ""
    return (
        f"- {record.get('title', '')} ({record.get('source', '')}) - {record.get('industry', '')}; mood {record.get('mood', '')}; layout {record.get('layout', '')}\n"
        f"  principles: {' | '.join(record.get('principles', [])) or 'none noted'}\n"
        f"  tokens: {colours}; fonts {', '.join(tokens.get('fonts', []))}; sections {' > '.join(record.get('sections', []))}{thumbnail}"
    )


def describe_use(record: dict[str, Any]) -> str:
    return f"- {record.get('added', '')}: accent {record.get('primary', '?')}, background {record.get('neutral', '?')}, fonts {' + '.join(record.get('fonts', [])) or '?'}, composition {record.get('composition') or '?'}"


class DesignKbAdd(Tool):
    name = "design_kb_add"
    read_only = False
    description = (
        "Keep a design reference you looked at with design_inspire in DebCraft's design knowledge base (shared by all projects, in the user's profile) so "
        "later projects can find it by industry, mood and layout. Give the page's slug (the file name in .forge/inspiration without the extension), the "
        "industry and mood in a few words, the layout in a few words, and the principles worth reusing (never the brand's own words, logo, photographs or "
        "exact colours). Use it after you have filled the reference note."
    )

    class Args(ToolArgs):
        slug: str = Field(description="The page's file name stem in .forge/inspiration, e.g. kiln-co-1")
        industry: str = Field(description="The kind of business, e.g. 'pottery studio, craft classes'")
        mood: str = Field(description="The feeling in a few words, e.g. 'warm, handmade, calm'")
        layout: str = Field(
            description="The composition in a few words, e.g. 'split hero, ruled list, large numerals'"
        )
        principles: list[str] = Field(
            min_length=1, max_length=8, description="Reusable principles, one sentence each"
        )

    def summary(self, args: DesignKbAdd.Args) -> str:
        return f"keep reference {args.slug} in the design knowledge base"

    async def run(self, args: DesignKbAdd.Args, context: ToolContext) -> ToolResult:
        base = context.workspace.root / INSPIRATION
        styles = base / f"{args.slug}.styles.json"
        if not styles.is_file():
            return ToolResult(
                ok=False,
                content=f"No {args.slug}.styles.json in {INSPIRATION}: look at the page with design_inspire first.",
            )
        data = json.loads(styles.read_text(encoding="utf-8"))
        found = from_computed(data)
        reference = add_reference(
            {
                "id": _slug(args.slug),
                "title": str(data.get("title", ""))[:100] or args.slug,
                "source": _source_of(base / f"{args.slug}.design.md"),
                "industry": args.industry,
                "mood": args.mood,
                "layout": args.layout,
                "principles": [p.strip() for p in args.principles],
                "tokens": {"colors": found.colors, "fonts": found.fonts[:3], "scale": data.get("scale", {})},
                "sections": [str(s.get("heading") or s.get("tag")) for s in data.get("sections", [])][:12],
            },
            base / f"{args.slug}.png",
        )
        return ToolResult(
            ok=True, content=f"Kept {reference['id']} ({args.industry}; {args.mood}) for later projects."
        )


def _source_of(draft: Path) -> str:
    try:
        match = re.search(r"https?://[^\s)\"']+", draft.read_text(encoding="utf-8"))
    except OSError:
        return ""
    return match.group(0) if match else ""


class DesignKbSearch(Tool):
    name = "design_kb_search"
    read_only = True
    description = (
        "Search DebCraft's design knowledge base (earlier references, shared by all projects) by industry, mood and layout words, and see the palettes, "
        "font pairs and compositions the last few designs used so that a new design does not repeat them. Use it at the start of a design, before the "
        "candidates; an empty result means nothing is stored yet."
    )

    class Args(ToolArgs):
        query: str = Field(
            min_length=2, description="Industry, mood and layout words, e.g. 'pottery studio warm editorial'"
        )
        limit: int = Field(default=5, ge=1, le=10)

    def summary(self, args: DesignKbSearch.Args) -> str:
        return f"search design knowledge: {args.query[:50]}"

    async def run(self, args: DesignKbSearch.Args, context: ToolContext) -> ToolResult:
        found = search_references(args.query, args.limit)
        uses = recent_uses()
        lines = (
            [f"{len(found)} reference(s) for '{args.query}':", *(describe_reference(r) for r in found)]
            if found
            else ["No stored reference matches."]
        )
        if uses:
            lines += [
                "",
                "Recent designs used these (choose differently unless the brief fixes it):",
                *(describe_use(u) for u in uses),
            ]
        return ToolResult(ok=True, content="\n".join(lines))


def design_knowledge_tools() -> list[Tool]:
    return [DesignKbAdd(), DesignKbSearch()]
