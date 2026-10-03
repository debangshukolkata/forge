"""Auto-memory (spec §12.6 as amended by D-156), modelled on Claude Code's memory: one Markdown file per
memory with a small frontmatter (name, description, type) and a `MEMORY.md` index, in two scopes.

- user scope, `<forge_home>/memory/`: preferences that apply everywhere ("always ask before adding a
  dependency");
- project scope, `<forge_home>/memory/scopes/<scope>/`: what Forge learned about one repository or host
  profile (see forge.memory.scope). Nothing crosses between projects.

The model writes memories itself (memory_write) when the user states something lasting or corrects it. The
index
(name, type, description) is pinned in every session; the model reads a memory in full with memory_read.
Memories are redacted before saving: they never hold secrets or data rows.

Custom slash commands (<forge_home>/commands/<name>.md): the file's text becomes the message, with
$ARGUMENTS replaced by whatever follows the command.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from forge.memory.scope import project_dir
from forge.safety.redact import default_redactor

KINDS = ("user", "feedback", "project", "reference")
MAX_BODY_CHARS = 4000
MAX_DESCRIPTION_CHARS = 150
INDEX_FILE = "MEMORY.md"
INSTRUCTIONS_FILE = "FORGE.md"  # shares the project folder with the notes but is not one of them (D-199)
STATE_MEMORY = "project-state"  # where a session leaves the state of the work for the next one (D-171)
_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")
_FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40].strip("-")
    return slug if _NAME.match(slug) else f"note-{datetime.now():%Y%m%d%H%M%S}"


@dataclass
class Memory:
    name: str
    description: str
    kind: str
    text: str
    scope: str = "user"  # "user" or the project scope key

    def render(self) -> str:
        return f"{self.name} ({self.kind}): {self.description}"


class MemoryStore:
    def __init__(self, home: Path, scope: str | None = None) -> None:
        base = home / "memory"
        self.scope = scope or "user"
        self.folder = base if scope is None else project_dir(home, scope)

    def _parse(self, path: Path) -> Memory:
        text = path.read_text(encoding="utf-8")
        match = _FRONT.match(text)
        if match:  # current format
            meta = dict(re.findall(r"^(\w+):\s*(.*)$", match.group(1), re.M))
            kind = meta.get("type", "user")
            return Memory(
                meta.get("name", path.stem),
                meta.get("description", ""),
                kind if kind in KINDS else "user",
                match.group(2).strip(),
                self.scope,
            )
        title, _, body = text.strip().partition("\n")  # older format: "# title" then the text
        return Memory(path.stem, title.lstrip("# ").strip(), "user", body.strip() or title, self.scope)

    def all(self) -> list[Memory]:
        if not self.folder.is_dir():
            return []
        return [
            self._parse(p)
            for p in sorted(self.folder.glob("*.md"))
            if p.name not in (INDEX_FILE, INSTRUCTIONS_FILE)
        ]

    def get(self, name: str) -> Memory | None:
        return next((m for m in self.all() if m.name == name), None)

    def save(self, name: str, description: str, kind: str, body: str) -> Memory:
        """Creates or replaces the memory called `name`."""
        text = default_redactor.redact(body.strip())[:MAX_BODY_CHARS]
        summary = " ".join(default_redactor.redact(description).split())[:MAX_DESCRIPTION_CHARS]
        if not text:
            raise ValueError("Nothing to remember.")
        if kind not in KINDS:
            raise ValueError(f"type must be one of {', '.join(KINDS)}.")
        slug = slugify(name)
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / f"{slug}.md"
        path.write_text(
            f"---\nname: {slug}\ndescription: {summary}\ntype: {kind}\n---\n\n{text}\n", encoding="utf-8"
        )
        self._write_index()
        return Memory(slug, summary, kind, text, self.scope)

    def add(self, text: str) -> Memory:
        """A quick user preference (the /remember command): the first line becomes the description."""
        clean = text.strip()
        first = clean.splitlines()[0] if clean else ""
        return self.save(slugify(first) if first else "", first, "user", clean)

    def delete(self, name: str) -> bool:
        path = self.folder / f"{name}.md"
        if not _NAME.match(name) or name == "memory" or not path.exists():
            return False
        path.unlink()
        self._write_index()
        return True

    def _write_index(self) -> None:
        lines = [f"- [{m.name}]({m.name}.md) ({m.kind}) — {m.description}" for m in self.all()]
        (self.folder / INDEX_FILE).write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def index(self) -> str | None:
        memories = self.all()
        return "\n".join(f"- {m.render()}" for m in memories) if memories else None


def combined_index(home: Path, scope: str | None) -> str | None:
    """The pinned memory index (spec §10.2): user memories plus this project's (names and descriptions)."""
    parts = []
    user = MemoryStore(home).index()
    if user:
        parts.append("About the user (all projects):\n" + user)
    project_store = MemoryStore(home, scope) if scope else None
    project = project_store.index() if project_store else None
    if project:
        parts.append("About this project:\n" + project)
    if project_store is not None and project_store.get(STATE_MEMORY) is not None:
        parts.insert(
            0,
            f"Work on this project was left unfinished or paused: read the memory '{STATE_MEMORY}' first "
            f"(memory_read name={STATE_MEMORY} scope=project) and carry on from there.",
        )
    if not parts:
        return None
    return "Saved memories (read one in full with memory_read):\n" + "\n".join(parts)


class CommandStore:
    def __init__(self, home: Path) -> None:
        self.folder = home / "commands"

    def names(self) -> list[str]:
        if not self.folder.exists():
            return []
        return sorted(p.stem for p in self.folder.glob("*.md") if _NAME.match(p.stem))

    def expand(self, name: str, arguments: str) -> str | None:
        """The message a custom command stands for, or None when there is no such command."""
        if not _NAME.match(name):
            return None
        path = self.folder / f"{name}.md"
        if not path.exists():
            return None
        template = path.read_text(encoding="utf-8")
        return template.replace("$ARGUMENTS", arguments.strip()).strip()
