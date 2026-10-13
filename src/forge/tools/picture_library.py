"""The local picture library (TODO D5, D-329): every picture `fetch_image` saved is kept in DebCraft's home folder with its licence, so
the next project can use it without the network. It grows by use; the bundled icons (Lucide, Material) are the part that ships.

Layout: `<forge home>/library/pictures/<file>` and `index.json` (a list of records: id, title, source, licence, author, credit, page,
file, tags). Writes go to DebCraft's own folder only, never into a project."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from forge.config import forge_home

MAX_ENTRIES = 2000


def folder() -> Path:
    return forge_home() / "library" / "pictures"


def _index_file() -> Path:
    return folder() / "index.json"


def load() -> list[dict[str, str]]:
    try:
        data = json.loads(_index_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [r for r in data if isinstance(r, dict) and (folder() / r.get("file", "?")).is_file()]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "picture"


def remember(record: dict[str, str], data: bytes, extension: str, query: str = "") -> None:
    """Keeps a copy of a fetched picture. `record` has id, title, source, licence, author, credit, page; `query` adds search words."""
    entries = [r for r in load() if r.get("id") != record["id"]]
    name = f"{_slug(record['source'])}-{_slug(record['title'])}-{hashlib.sha1(record['id'].encode()).hexdigest()[:6]}{extension}"
    folder().mkdir(parents=True, exist_ok=True)
    (folder() / name).write_bytes(data)
    entries.append(
        {
            **record,
            "file": name,
            "tags": " ".join({*re.findall(r"[a-z0-9]+", f"{record['title']} {query}".lower())}),
        }
    )
    for old in entries[:-MAX_ENTRIES]:  # the oldest go first
        (folder() / old["file"]).unlink(missing_ok=True)
    _index_file().write_text(json.dumps(entries[-MAX_ENTRIES:], indent=1), encoding="utf-8")


def search(query: str, limit: int) -> list[dict[str, str]]:
    words = {w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2}
    scored = []
    for record in load():
        tags = set(record.get("tags", "").split())
        score = len(words & tags)
        if score:
            scored.append((score, record))
    scored.sort(key=lambda row: -row[0])
    return [r for _, r in scored[:limit]]
