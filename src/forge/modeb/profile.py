"""Host Profiles (spec §6A.2): the Mode B equivalent of the knowledge base — what Forge knows about a host
codebase it may not see, built from the interview, an imported structure export and approved snippets.

<forge_home>/profiles/<name>/
  profile.json            name, version, sensitive_terms, created/updated
  PROFILE.md              the structured interview answers (sections 1-7)
  CONVENTIONS.md, INTERFACES.md
  exemplars/<id>.py (+ <id>.md: what it demonstrates)
  structure_export.json   the latest imported export; structure_index.json its search documents
  CHANGELOG.md

Everything written is redacted first. The export is never sent to the model wholesale: search() returns
only the modules relevant to a query. Every change bumps the version and is logged.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from forge.kb.bm25 import BM25, tokenize
from forge.safety.redact import default_redactor

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,48}$")
SECTIONS = (
    "Stack & versions",
    "Structure",
    "App wiring",
    "Conventions",
    "Data",
    "LLM layer",
    "Testing",
)
DOCUMENTS = ("PROFILE", "CONVENTIONS", "INTERFACES")


class ProfileError(ValueError):
    pass


@dataclass
class ImportReport:
    modules: int
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    sensitive_hits: list[str] = field(default_factory=list)  # sensitive terms found (they were masked)
    redacted: bool = False

    def summary(self) -> str:
        parts = [f"{self.modules} module(s)"]
        if self.added or self.removed or self.changed:
            parts.append(f"{len(self.added)} added, {len(self.removed)} removed, {len(self.changed)} changed")
        if self.sensitive_hits:
            parts.append(f"sensitive terms masked: {', '.join(self.sensitive_hits)}")
        if self.redacted:
            parts.append("secret-looking values were redacted")
        return "; ".join(parts)


class HostProfile:
    def __init__(self, root: Path) -> None:
        self.root = root

    @property
    def name(self) -> str:
        return self.root.name

    # --- metadata ---

    def meta(self) -> dict[str, Any]:
        path = self.root / "profile.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    @property
    def version(self) -> int:
        return int(self.meta().get("version", 0))

    @property
    def sensitive_terms(self) -> list[str]:
        return list(self.meta().get("sensitive_terms", []))

    def set_sensitive_terms(self, terms: list[str]) -> None:
        self._bump("sensitive terms updated", sensitive_terms=sorted({t.strip() for t in terms if t.strip()}))

    def _bump(self, change: str, **fields: Any) -> None:
        meta = self.meta() | fields
        meta["version"] = int(meta.get("version", 0)) + 1
        meta["updated"] = datetime.now().isoformat(timespec="seconds")
        (self.root / "profile.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        with (self.root / "CHANGELOG.md").open("a", encoding="utf-8") as log:
            log.write(f"- v{meta['version']} {meta['updated']}: {change}\n")

    # --- documents ---

    def read(self, document: str) -> str:
        if document not in DOCUMENTS:
            raise ProfileError(f"Unknown profile document {document!r}; one of {', '.join(DOCUMENTS)}")
        path = self.root / f"{document}.md"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def write(self, document: str, text: str, change: str) -> None:
        """Only after the user approved the change (the caller shows it)."""
        if document not in DOCUMENTS:
            raise ProfileError(f"Unknown profile document {document!r}")
        (self.root / f"{document}.md").write_text(self.clean(text), encoding="utf-8")
        self._bump(f"{document}: {change}")

    def clean(self, text: str) -> str:
        """Redaction + the profile's sensitive terms, before anything is stored."""
        cleaned = default_redactor.redact(text)
        for index, term in enumerate(self.sensitive_terms, 1):
            cleaned = re.sub(re.escape(term), f"<term{index}>", cleaned, flags=re.IGNORECASE)
        return cleaned

    def sensitive_hits(self, text: str) -> list[str]:
        return [t for t in self.sensitive_terms if re.search(re.escape(t), text, re.IGNORECASE)]

    # --- exemplars ---

    def exemplars(self) -> list[tuple[str, str]]:
        folder = self.root / "exemplars"
        if not folder.exists():
            return []
        return [
            (
                p.stem,
                (p.with_suffix(".md").read_text(encoding="utf-8") if p.with_suffix(".md").exists() else ""),
            )
            for p in sorted(folder.glob("*.py"))
        ]

    def add_exemplar(self, code: str, note: str) -> tuple[str, bool]:
        """Stores an approved snippet; returns (id, whether redaction changed it — the caller warns)."""
        cleaned = self.clean(code)
        folder = self.root / "exemplars"
        folder.mkdir(exist_ok=True)
        exemplar_id = f"E{len(list(folder.glob('*.py'))) + 1:03d}"
        (folder / f"{exemplar_id}.py").write_text(cleaned, encoding="utf-8")
        (folder / f"{exemplar_id}.md").write_text(self.clean(note), encoding="utf-8")
        self._bump(f"exemplar {exemplar_id} added: {note[:60]}")
        return exemplar_id, cleaned != code

    def read_exemplar(self, exemplar_id: str) -> str | None:
        path = self.root / "exemplars" / f"{exemplar_id}.py"
        return (
            path.read_text(encoding="utf-8")
            if re.fullmatch(r"E\d{3}", exemplar_id) and path.exists()
            else None
        )

    def forget_exemplar(self, exemplar_id: str) -> bool:
        """/forget-snippet: removes the snippet and its note from the profile."""
        if not re.fullmatch(r"E\d{3}", exemplar_id):
            return False
        removed = False
        for suffix in (".py", ".md"):
            path = self.root / "exemplars" / f"{exemplar_id}{suffix}"
            if path.exists():
                path.unlink()
                removed = True
        if removed:
            self._bump(f"exemplar {exemplar_id} forgotten")
        return removed

    # --- structure export ---

    def import_structure(self, data: dict[str, Any]) -> ImportReport:
        if data.get("format") != "forge-structure-export" or not isinstance(data.get("modules"), dict):
            raise ProfileError("Not a Forge structure export (run forge_structure_export.py on the host).")
        raw = json.dumps(data)
        hits = self.sensitive_hits(raw)
        cleaned_text = self.clean(raw)
        cleaned: dict[str, Any] = json.loads(cleaned_text)
        previous = self.structure()
        report = ImportReport(
            modules=len(cleaned["modules"]), sensitive_hits=hits, redacted=default_redactor.redact(raw) != raw
        )
        if previous:
            old, new = previous.get("modules", {}), cleaned["modules"]
            report.added = sorted(set(new) - set(old))
            report.removed = sorted(set(old) - set(new))
            report.changed = sorted(m for m in set(new) & set(old) if new[m] != old[m])
        (self.root / "structure_export.json").write_text(json.dumps(cleaned, indent=1), encoding="utf-8")
        (self.root / "structure_index.json").write_text(json.dumps(_documents(cleaned)), encoding="utf-8")
        self._bump(f"structure export imported ({report.summary()})")
        return report

    def structure(self) -> dict[str, Any]:
        path = self.root / "structure_export.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def search(self, query: str, limit: int = 6) -> list[tuple[str, str]]:
        """(module path, compact description) of the modules most relevant to the query."""
        path = self.root / "structure_index.json"
        if not path.exists():
            return []
        documents: list[list[str]] = json.loads(path.read_text(encoding="utf-8"))
        index = BM25([tokenize(text) for _, text in documents])
        scored = sorted(zip(index.scores(tokenize(query)), documents, strict=True), key=lambda x: -x[0])
        return [(doc[0], doc[1]) for score, doc in scored[:limit] if score > 0]

    def packages(self) -> dict[str, str]:
        packages: dict[str, str] = self.structure().get("packages", {})
        return packages

    # --- the whole profile, compact (pinned in Mode B sessions) ---

    def essentials(self, max_chars: int = 6000) -> str:
        parts = [f"Host profile '{self.name}' v{self.version}."]
        profile = self.read("PROFILE")
        if profile:
            parts.append(profile)
        conventions = self.read("CONVENTIONS")
        if conventions:
            parts.append("Conventions:\n" + conventions)
        exemplars = self.exemplars()
        if exemplars:
            parts.append(
                "Exemplars (profile_read exemplar <id>): " + "; ".join(f"{i}: {n[:80]}" for i, n in exemplars)
            )
        if self.structure():
            parts.append(
                f"A structure export of {len(self.structure().get('modules', {}))} modules is "
                f"indexed: search it "
                "with profile_search (signatures, blueprints, models, env key names — never code)."
            )
        text = "\n\n".join(parts)
        return text if len(text) <= max_chars else text[:max_chars] + "\n[… see profile_read for the rest …]"


def _documents(export: dict[str, Any]) -> list[list[str]]:
    documents = []
    for path, module in export.get("modules", {}).items():
        if "error" in module:
            continue
        lines = [path, "imports: " + ", ".join(module.get("imports", [])[:30])]
        for cls in module.get("classes", []):
            lines.append(f"class {cls['name']}({', '.join(cls['bases'])})")
            lines += [f"  {m['signature']}" for m in cls.get("methods", [])]
        lines += [f"def {f['signature']}" for f in module.get("functions", [])]
        for bp in module.get("blueprints", []):
            routes = ", ".join(f"{'/'.join(r['methods'])} {r['path']}" for r in bp.get("routes", []))
            lines.append(f"blueprint {bp.get('name')} {bp.get('url_prefix') or ''}: {routes}")
        for model in module.get("models", []):
            cols = ", ".join(f"{c['name']} {c['type']}" for c in model.get("columns", []))
            lines.append(f"model {model['class']} table {model.get('table')}: {cols}")
        if module.get("env_keys"):
            lines.append("env keys: " + ", ".join(module["env_keys"]))
        graph = module.get("graph") or {}
        if graph.get("nodes"):
            lines.append("graph: " + ", ".join(graph["nodes"]) + " | " + ", ".join(graph.get("edges", [])))
        documents.append([path, "\n".join(lines)])
    return documents


class ProfileStore:
    def __init__(self, home: Path) -> None:
        self.root = home / "profiles"

    def names(self) -> list[str]:
        return (
            sorted(p.name for p in self.root.iterdir() if (p / "profile.json").exists())
            if self.root.exists()
            else []
        )

    def open(self, name: str) -> HostProfile:
        if not _NAME.match(name) or not (self.root / name / "profile.json").exists():
            raise ProfileError(
                f"No host profile named {name!r}. Profiles: {', '.join(self.names()) or 'none'}"
            )
        return HostProfile(self.root / name)

    def create(self, name: str, sensitive_terms: list[str] | None = None) -> HostProfile:
        if not _NAME.match(name):
            raise ProfileError("Profile names use letters, digits, - and _ (up to 49 characters).")
        root = self.root / name
        if (root / "profile.json").exists():
            raise ProfileError(f"A profile named {name!r} already exists.")
        root.mkdir(parents=True)
        created = datetime.now().isoformat(timespec="seconds")
        (root / "profile.json").write_text(
            json.dumps(
                {"name": name, "version": 0, "sensitive_terms": sensitive_terms or [], "created": created}
            ),
            encoding="utf-8",
        )
        profile = HostProfile(root)
        skeleton = "\n\n".join(f"## {i}. {title}\n\n(unknown)" for i, title in enumerate(SECTIONS, 1))
        (root / "PROFILE.md").write_text(f"# Host profile: {name}\n\n{skeleton}\n", encoding="utf-8")
        profile._bump("profile created")
        return profile


def host_identifying_terms(profile: HostProfile | None) -> tuple[str, ...]:
    """Words a web query must never contain (spec §6A.8): the profile's sensitive terms, the host's top-level
    package names and its table names (from the structure export)."""
    if profile is None:
        return ()
    terms = set(profile.sensitive_terms)
    structure = profile.structure()
    for path, module in structure.get("modules", {}).items():
        top = path.split("/")[0]
        if top.endswith(".py"):
            continue
        if top not in {"tests", "test", "docs", "scripts", "migrations", "sql"}:
            terms.add(top)
        for model in module.get("models", []) if isinstance(module, dict) else []:
            if model.get("table"):
                terms.add(str(model["table"]))
    return tuple(sorted(t for t in terms if len(t) >= 4))
