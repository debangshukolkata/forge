"""The requirements library (spec §12.2): one "requirement card" per workspace, written at EXPORT, searchable
(BM25 over the text plus path overlap) only by workspaces in the same scope (repository or host profile).

<forge_home>/library/cards.json   index: id, scope, workspace, title, paths, status, created
<forge_home>/library/<id>.md      the card: goal, approach, decisions, files, endpoints/tables,
                                  problems, status
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from forge.kb.bm25 import BM25, tokenize
from forge.safety.paths import resolve_inside
from forge.safety.redact import default_redactor

ENDPOINT = re.compile(r"(?:GET|POST|PUT|PATCH|DELETE)\s+(/[\w/<>{}:.-]*)")
TABLE = re.compile(r"(?:create|alter)\s+table\s+(?:if\s+(?:not\s+)?exists\s+)?([\w.\"]+)", re.IGNORECASE)


@dataclass
class CardHit:
    id: str
    title: str
    score: float
    snippet: str


class Library:
    def __init__(self, home: Path) -> None:
        self.root = home / "library"

    def _index(self) -> list[dict[str, Any]]:
        path = self.root / "cards.json"
        entries: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        return entries

    def _save_index(self, entries: list[dict[str, Any]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "cards.json").write_text(json.dumps(entries, indent=1), encoding="utf-8")

    def write_card(
        self,
        *,
        scope: str,
        workspace_root: str,
        workspace_name: str,
        requirement: str,
        plan: str,
        decisions: str,
        tasks: list[dict[str, Any]],
        files: list[str],
        sql: str,
        status: str,
        problems: list[str],
    ) -> str:
        """Creates (or updates, for the same workspace) the card; returns its id (REQ-0001...)."""
        entries = self._index()
        existing = next((e for e in entries if e["workspace"] == workspace_root), None)
        card_id = existing["id"] if existing else f"REQ-{len(entries) + 1:04d}"
        title = _title(requirement)
        endpoints = sorted(set(ENDPOINT.findall(requirement + "\n" + plan)))
        tables = sorted({t.strip('"') for t in TABLE.findall(sql)})
        lines = [
            f"# {card_id}: {title}",
            "",
            f"Workspace: {workspace_name} · status: {status} · {datetime.now():%Y-%m-%d}",
            "",
            "## Goal",
            requirement.strip(),
            "",
            "## Approach (plan)",
            plan.strip()[:4000] or "(no plan recorded)",
            "",
            "## Key decisions",
            decisions.strip()[:3000] or "(none recorded)",
            "",
            "## Tasks",
            *[f"- {t['id']} [{t['status']}] {t['title']}" for t in tasks],
            "",
            "## Files added/modified",
            *[f"- {f}" for f in files],
            "",
            "## Endpoints / tables touched",
            *([f"- {e}" for e in endpoints] + [f"- table {t}" for t in tables] or ["- none detected"]),
            "",
            "## Problems hit and how they were fixed",
            *([f"- {p}" for p in problems] or ["- none recorded"]),
        ]
        text = default_redactor.redact("\n".join(lines) + "\n")
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / f"{card_id}.md").write_text(text, encoding="utf-8")
        entry = {
            "id": card_id,
            "scope": scope,
            "workspace": workspace_root,
            "title": title,
            "paths": files,
            "status": status,
            "created": existing["created"] if existing else datetime.now().isoformat(timespec="seconds"),
        }
        entries = [e for e in entries if e["id"] != card_id] + [entry]
        self._save_index(entries)
        return card_id

    def cards(self, scopes: tuple[str, ...]) -> list[dict[str, Any]]:
        return [e for e in self._index() if e["scope"] in scopes]

    def read(self, card_id: str, scopes: tuple[str, ...]) -> str | None:
        entry = next((e for e in self.cards(scopes) if e["id"].upper() == card_id.upper()), None)
        if entry is None:
            return None  # unknown, or in another repository/profile: invisible
        return (self.root / f"{entry['id']}.md").read_text(encoding="utf-8")

    def search(
        self,
        query: str,
        scopes: tuple[str, ...],
        paths: list[str] | None = None,
        limit: int = 5,
        exclude: str = "",
    ) -> list[CardHit]:
        entries = [e for e in self.cards(scopes) if e["workspace"] != exclude]
        if not entries:
            return []
        texts = [(self.root / f"{e['id']}.md").read_text(encoding="utf-8") for e in entries]
        scores = BM25([tokenize(t) for t in texts]).scores(tokenize(query))
        wanted = {p.rsplit("/", 1)[0] for p in paths or []}
        hits = []
        for entry, text, score in zip(entries, texts, scores, strict=True):
            overlap = len(wanted & {p.rsplit("/", 1)[0] for p in entry["paths"]})
            total = score + overlap
            if total > 0:
                snippet = text.split("## Approach", 1)[0].strip()[-400:]
                hits.append(CardHit(entry["id"], entry["title"], round(total, 3), snippet))
        return sorted(hits, key=lambda h: -h.score)[:limit]

    def read_workspace_file(self, card_id: str, relative: str, scopes: tuple[str, ...]) -> str | None:
        """library_read: a past workspace's file, read-only, same scope only."""
        entry = next((e for e in self.cards(scopes) if e["id"].upper() == card_id.upper()), None)
        if entry is None:
            return None
        root = Path(entry["workspace"])
        for folder in ("repo", "project"):
            base = root / folder
            if base.is_dir():
                path = resolve_inside(base, relative)
                if path.is_file():
                    return path.read_text(encoding="utf-8", errors="replace")
        return None

    def overlaps(
        self, files: list[str], scopes: tuple[str, ...], exclude: str
    ) -> list[tuple[str, list[str]]]:
        """Earlier requirements (not integrated yet) that modified the same files (spec §12.2)."""
        wanted = set(files)
        result = []
        for entry in self.cards(scopes):
            if entry["workspace"] == exclude or entry.get("status") == "integrated":
                continue
            shared = sorted(wanted & set(entry["paths"]))
            if shared:
                result.append((entry["id"], shared))
        return result


def _title(requirement: str) -> str:
    first = requirement.strip().splitlines()[0] if requirement.strip() else "Untitled requirement"
    return (first[:90] + "…") if len(first) > 90 else first
