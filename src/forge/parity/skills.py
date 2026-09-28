"""Skills (spec §13B): Markdown instruction packs. Built-in ones ship in forge/skills/<name>/SKILL.md;
users add their own in <forge_home>/skills/<name>/ and per repo/profile in <kb or profile>/skills/<name>/
(later ones override earlier ones of the same name). Only each skill's one-line description is pinned;
the model loads a full skill with load_skill(name) when a task matches."""

from __future__ import annotations

import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


@dataclass
class Skill:
    name: str
    description: str
    path: Path

    def body(self) -> str:
        text = self.path.read_text(encoding="utf-8")
        return FRONT.sub("", text, count=1).strip()


def _parse(path: Path) -> Skill | None:
    text = path.read_text(encoding="utf-8")
    match = FRONT.match(text)
    meta = dict(re.findall(r"^(\w+):\s*(.+)$", match.group(1), re.M)) if match else {}
    name = meta.get("name", path.parent.name).strip()
    description = meta.get("description", text.strip().splitlines()[0] if text.strip() else "").strip()
    return Skill(name, description, path) if name else None


def discover(*roots: Path | None) -> dict[str, Skill]:
    builtin = Path(str(resources.files("forge") / "skills"))
    skills: dict[str, Skill] = {}
    for root in (builtin, *roots):
        if root is None or not root.is_dir():
            continue
        for skill_file in sorted(root.glob("*/SKILL.md")):
            skill = _parse(skill_file)
            if skill is not None:
                skills[skill.name] = skill
    return skills


def index_text(skills: dict[str, Skill]) -> str | None:
    if not skills:
        return None
    lines = [f"- {s.name}: {s.description}" for s in sorted(skills.values(), key=lambda s: s.name)]
    return "Skills (load one with load_skill when a task matches):\n" + "\n".join(lines)
