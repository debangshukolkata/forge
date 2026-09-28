"""User memory (spec §12.6): preferences that apply across all repositories ("always ask before adding a
dependency", "use type hints"), one Markdown file per memory in <forge_home>/memory/. Their titles are
pinned in every session (the memory index); the model reads a memory in full with memory_read. Memories
are redacted before saving: they never hold secrets.

Custom slash commands (<forge_home>/commands/<name>.md): the file's text becomes the message, with
$ARGUMENTS replaced by whatever follows the command.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from forge.safety.redact import default_redactor

MAX_MEMORY_CHARS = 2000
_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,40}$")


@dataclass
class Memory:
    id: str
    title: str
    text: str

    def render(self) -> str:
        return f"{self.id}: {self.title}"


class MemoryStore:
    def __init__(self, home: Path) -> None:
        self.folder = home / "memory"

    def all(self) -> list[Memory]:
        if not self.folder.exists():
            return []
        memories = []
        for path in sorted(self.folder.glob("*.md")):
            text = path.read_text(encoding="utf-8").strip()
            title, _, body = text.partition("\n")
            memories.append(Memory(path.stem, title.lstrip("# ").strip(), body.strip() or title))
        return memories

    def get(self, memory_id: str) -> Memory | None:
        return next((m for m in self.all() if m.id == memory_id), None)

    def add(self, text: str) -> Memory:
        clean = default_redactor.redact(text.strip())[:MAX_MEMORY_CHARS]
        if not clean:
            raise ValueError("Nothing to remember.")
        title = clean.splitlines()[0][:80]
        memory_id = f"M{datetime.now():%Y%m%d%H%M%S%f}"[:18]
        self.folder.mkdir(parents=True, exist_ok=True)
        (self.folder / f"{memory_id}.md").write_text(f"# {title}\n\n{clean}\n", encoding="utf-8")
        return Memory(memory_id, title, clean)

    def delete(self, memory_id: str) -> bool:
        path = self.folder / f"{memory_id}.md"
        if not re.fullmatch(r"M\d+", memory_id) or not path.exists():
            return False
        path.unlink()
        return True

    def index(self) -> str | None:
        """The pinned memory index: titles only (spec §10.2)."""
        memories = self.all()
        if not memories:
            return None
        lines = [f"- {m.render()}" for m in memories]
        return "The user asked Forge to remember (read one in full with memory_read):\n" + "\n".join(lines)


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
