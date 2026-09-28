"""Reading a built Knowledge Base (spec §11.5): search, documents, symbols, references, essentials."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from forge.kb.bm25 import BM25, tokenize
from forge.kb.store import load_manifest

SNIPPET_CHARS = 500


@dataclass
class SearchHit:
    kind: str  # doc | symbol
    name: str  # document name or qualified symbol
    location: str  # section title or file:line
    snippet: str
    score: float


class KnowledgeBase:
    def __init__(self, kb_dir: Path) -> None:
        self.kb_dir = kb_dir
        self._sections: list[tuple[str, str, str]] | None = None  # (doc, section title, text)
        self._index: BM25 | None = None

    @classmethod
    def open(cls, kb_dir: Path) -> KnowledgeBase | None:
        return cls(kb_dir) if (kb_dir / "manifest.json").exists() else None

    @property
    def manifest(self):  # type: ignore[no-untyped-def]
        return load_manifest(self.kb_dir)

    def credential_tables(self) -> list[str]:
        manifest = load_manifest(self.kb_dir)
        return manifest.credential_tables if manifest else []

    # --- documents ---

    def doc_names(self) -> list[str]:
        return sorted(
            p.relative_to(self.kb_dir).with_suffix("").as_posix()
            for p in self.kb_dir.rglob("*.md")
            if p.name != "ESSENTIALS.md"
        )

    def read(self, name: str) -> str | None:
        clean = name.removesuffix(".md").strip("/")
        path = (self.kb_dir / f"{clean}.md").resolve()
        if not path.is_relative_to(self.kb_dir.resolve()) or not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def essentials(self) -> str | None:
        path = self.kb_dir / "ESSENTIALS.md"
        return path.read_text(encoding="utf-8") if path.exists() else None

    # --- search ---

    def search(self, query: str, kinds: list[str] | None = None, limit: int = 8) -> list[SearchHit]:
        """Docs and symbols are scored on different scales, so with both kinds the best documents come
        first and the best symbols fill the rest, rather than mixing the two rankings."""
        doc_hits: list[SearchHit] = []
        symbol_hits: list[SearchHit] = []
        if not kinds or "doc" in kinds:
            sections = self._doc_sections()
            if self._index is None:
                self._index = BM25([tokenize(f"{doc} {title} {text}") for doc, title, text in sections])
            scores = self._index.scores(tokenize(query))
            for (doc, title, text), score in zip(sections, scores, strict=True):
                if score > 0:
                    doc_hits.append(SearchHit("doc", doc, title, text.strip()[:SNIPPET_CHARS], score))
        if not kinds or "symbol" in kinds:
            symbol_hits = self._symbol_hits(query)
        doc_hits.sort(key=lambda h: h.score, reverse=True)
        symbol_hits.sort(key=lambda h: h.score, reverse=True)
        if doc_hits and symbol_hits:
            doc_share = max(limit - limit // 3, limit - len(symbol_hits))
            return doc_hits[:doc_share] + symbol_hits[: limit - min(doc_share, len(doc_hits))]
        return (doc_hits or symbol_hits)[:limit]

    def _doc_sections(self) -> list[tuple[str, str, str]]:
        if self._sections is None:
            self._sections = []
            for name in self.doc_names():
                text = self.read(name) or ""
                title, current = name, list[str]()
                for line in text.splitlines():
                    if line.startswith("#") and current:
                        self._sections.append((name, title, "\n".join(current)))
                        current = []
                    if line.startswith("#"):
                        title = line.lstrip("# ").strip()
                    current.append(line)
                if current:
                    self._sections.append((name, title, "\n".join(current)))
        return self._sections

    def _symbol_hits(self, query: str) -> list[SearchHit]:
        words = set(tokenize(query))
        hits = []
        for row in self._rows("SELECT kind, qualname, path, line, signature, doc, name FROM symbols"):
            name_words = set(tokenize(row[6]))
            overlap = len(words & name_words)
            if overlap:
                score = 3.0 * overlap + (5.0 if row[6].lower() in {w.lower() for w in query.split()} else 0.0)
                hits.append(
                    SearchHit(
                        "symbol",
                        row[1],
                        f"{row[2]}:{row[3]}",
                        (row[4] or row[0]) + (f" — {row[5]}" if row[5] else ""),
                        score,
                    )
                )
        return hits

    # --- symbols ---

    def find_symbol(self, name: str) -> list[dict[str, object]]:
        rows = self._rows(
            "SELECT kind, qualname, module, path, line, end_line, signature, decorators, bases, doc "
            "FROM symbols WHERE name = ? OR qualname = ? OR qualname LIKE ? ORDER BY path, line",
            (name, name, f"%.{name}"),
        )
        keys = [
            "kind",
            "qualname",
            "module",
            "path",
            "line",
            "end_line",
            "signature",
            "decorators",
            "bases",
            "doc",
        ]
        results = [dict(zip(keys, row, strict=True)) for row in rows]
        for result in results:
            result["decorators"] = json.loads(str(result["decorators"]))
            result["bases"] = json.loads(str(result["bases"]))
        return results

    def find_references(self, name: str) -> list[tuple[str, int]]:
        short = name.split(".")[-1]
        return [
            (str(r[0]), int(r[1]))
            for r in self._rows("SELECT path, line FROM refs WHERE name = ? ORDER BY path, line", (short,))
        ]

    def list_symbols(self, path: str) -> list[tuple[str, str, int, str]]:
        rows = self._rows(
            "SELECT kind, qualname, line, signature FROM symbols WHERE path = ? ORDER BY line", (path,)
        )
        return [(str(r[0]), str(r[1]), int(r[2]), str(r[3] or "")) for r in rows]

    def _rows(self, sql: str, params: tuple[object, ...] = ()) -> list[tuple[Any, ...]]:
        index = self.kb_dir / "index.sqlite"
        if not index.exists():
            return []
        with closing(sqlite3.connect(f"file:{index}?mode=ro", uri=True)) as db:
            return list(db.execute(sql, params).fetchall())
