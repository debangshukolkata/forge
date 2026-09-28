"""On-disk KB layout (spec §11.1-11.2): Markdown docs, index.sqlite (symbols, references), manifest.json."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from forge.kb.facts import RepoFacts
from forge.safety.paths import real_path

PINNED_MARKER = "<!-- pinned -->"


def is_pinned(text: str) -> bool:
    """A document is pinned when one of its lines is exactly the marker (a mention inside other text,
    like the note on generated documents, does not count)."""
    return any(line.strip() == PINNED_MARKER for line in text.splitlines())


KB_FORMAT_VERSION = 1


class KbManifest(BaseModel):
    format_version: int = KB_FORMAT_VERSION
    repo_path: str
    app_subfolder: str
    built: str
    file_hashes: dict[str, str]
    packages: dict[str, list[str]]  # package -> files
    narrative_docs: list[str] = Field(default_factory=list)
    # Tables the app's credentials bootstrap reads (spec §9.5.1): Forge never reads their rows.
    credential_tables: list[str] = Field(default_factory=list)


def kb_dir_for(home: Path, repo_path: Path | str, app_subfolder: str) -> Path:
    """<forge_home>/kb/<repo-slug>-<hash>: one KB per repository app folder, shared by all workspaces."""
    resolved = str(real_path(repo_path)).lower()
    digest = hashlib.sha256(f"{resolved}|{app_subfolder}".encode()).hexdigest()[:10]
    slug = "".join(c if c.isalnum() else "-" for c in Path(resolved).name)[:40].strip("-") or "repo"
    return home / "kb" / f"{slug}-{digest}"


def load_manifest(kb_dir: Path) -> KbManifest | None:
    path = kb_dir / "manifest.json"
    return KbManifest.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None


def save_manifest(kb_dir: Path, facts: RepoFacts, narrative_docs: list[str]) -> KbManifest:
    manifest = KbManifest(
        repo_path=facts.repo_path,
        app_subfolder=facts.app_subfolder,
        built=datetime.now(UTC).isoformat(timespec="seconds"),
        file_hashes=facts.file_hashes,
        packages={package: [m.path for m in modules] for package, modules in facts.packages().items()},
        narrative_docs=sorted(narrative_docs),
        credential_tables=sorted({t.lower() for boot in facts.bootstraps for t in boot.tables}),
    )
    (kb_dir / "manifest.json").write_text(manifest.model_dump_json(indent=1), encoding="utf-8")
    return manifest


def doc_path(kb_dir: Path, name: str) -> Path:
    return kb_dir / f"{name}.md"


def write_doc(kb_dir: Path, name: str, text: str) -> bool:
    """False (and nothing written) if the user pinned the document by hand (spec §11.4)."""
    path = doc_path(kb_dir, name)
    if path.exists() and is_pinned(path.read_text(encoding="utf-8")):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


SCHEMA = """
CREATE TABLE symbols (kind TEXT, name TEXT, qualname TEXT, module TEXT, path TEXT, line INTEGER,
                      end_line INTEGER, signature TEXT, decorators TEXT, bases TEXT, doc TEXT);
CREATE TABLE refs (name TEXT, path TEXT, line INTEGER);
CREATE TABLE imports (module TEXT, path TEXT, source TEXT, name TEXT, alias TEXT, line INTEGER);
CREATE INDEX symbols_name ON symbols(name);
CREATE INDEX refs_name ON refs(name);
"""


def write_index(kb_dir: Path, facts: RepoFacts) -> None:
    path = kb_dir / "index.sqlite"
    temporary = path.with_suffix(".tmp")
    temporary.unlink(missing_ok=True)
    with closing(sqlite3.connect(temporary)) as db:
        db.executescript(SCHEMA)
        for module in facts.modules:
            db.executemany(
                "INSERT INTO symbols VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        s.kind,
                        s.name,
                        s.qualname,
                        s.module,
                        s.path,
                        s.line,
                        s.end_line,
                        s.signature,
                        json.dumps(s.decorators),
                        json.dumps(s.bases),
                        s.doc,
                    )
                    for s in module.symbols
                ],
            )
            db.executemany(
                "INSERT INTO refs VALUES (?,?,?)",
                [(name.split(".")[-1], module.path, line) for name, line in module.references],
            )
            db.executemany(
                "INSERT INTO imports VALUES (?,?,?,?,?,?)",
                [(module.module, module.path, i.module, i.name, i.alias, i.line) for i in module.imports],
            )
        db.commit()
    temporary.replace(path)  # readers never see a half-built index
