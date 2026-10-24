"""Skills (spec §13B): Markdown instruction packs. Built-in ones ship in forge/skills/<name>/SKILL.md;
users add their own in <forge_home>/skills/<name>/ and per repo/profile in
<project memory folder or profile>/skills/<name>/
(later ones override earlier ones of the same name). Only each skill's one-line description is pinned;
the model loads a full skill with load_skill(name) when a task matches."""

from __future__ import annotations

import os
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
    pack: str = ""  # the install this skill came from (D-480); skills of one pack share one line in the index
    own_design: bool = False  # it brings its own style guide (a diagram skill): the page design gate stands aside while it is loaded (D-483)

    @property
    def folder(self) -> Path:
        return self.path.parent

    def body(self) -> str:
        text = self.path.read_text(encoding="utf-8")
        return FRONT.sub("", text, count=1).strip()


def _parse(path: Path) -> Skill | None:
    text = path.read_text(encoding="utf-8")
    match = FRONT.match(text)
    meta = dict(re.findall(r"^(\w+):\s*(.+)$", match.group(1), re.M)) if match else {}
    name = meta.get("name", path.parent.name).strip()
    description = (
        meta.get("description", text.strip().splitlines()[0] if text.strip() else "").strip().strip("\"'")
    )
    own_design = meta.get("own_design", "").strip().lower() in ("true", "yes")
    return Skill(name, description, path, _pack_of(path, meta), own_design) if name else None


PACK_FILE = ".pack"
PACK_MIN_MEMBERS = 3  # fewer than this and a group line saves nothing: they are listed one by one
PACK_NAMES_SHOWN = 12


def _pack_of(skill_file: Path, meta: dict[str, str]) -> str:
    """A `.pack` file beside SKILL.md (written at install) wins over a `pack:` header line an author may have set."""
    marker = skill_file.parent / PACK_FILE
    try:
        named = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    except OSError:
        named = ""
    return named or meta.get("pack", "").strip().strip("\"'")


def set_pack(skill_folder: Path, pack: str) -> None:
    marker = skill_folder / PACK_FILE
    if pack:
        marker.write_text(pack + "\n", encoding="utf-8")
    elif marker.is_file():
        marker.unlink()


def disabled_names() -> set[str]:
    """Skills switched off for this process (`FORGE_DISABLED_SKILLS=name1,name2`): the A/B runs that measure what a skill is worth use it (C14, D-417)."""
    return {name.strip() for name in os.environ.get("FORGE_DISABLED_SKILLS", "").split(",") if name.strip()}


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
    for name in disabled_names():
        skills.pop(name, None)
    return skills


def packs(skills: dict[str, Skill]) -> dict[str, list[Skill]]:
    """Packs big enough to be shown as one line. A pack name that is also a skill name never hides that skill."""
    grouped: dict[str, list[Skill]] = {}
    for skill in skills.values():
        if skill.pack and skill.pack not in skills:
            grouped.setdefault(skill.pack, []).append(skill)
    return {
        name: sorted(members, key=lambda s: s.name)
        for name, members in grouped.items()
        if len(members) >= PACK_MIN_MEMBERS
    }


def pack_listing(pack: str, members: list[Skill]) -> str:
    """What load_skill(<pack name>) returns: every member with its full description."""
    lines = [f"- {s.name}: {s.description}" for s in members]
    return (
        f"Pack {pack} ({len(members)} skills). Load the one that fits with load_skill(name):\n"
        + "\n".join(lines)
    )


def index_text(skills: dict[str, Skill]) -> str | None:
    if not skills:
        return None
    grouped = packs(skills)
    inside = {s.name for members in grouped.values() for s in members}
    lines = [
        f"- {s.name}: {s.description}"
        for s in sorted(skills.values(), key=lambda s: s.name)
        if s.name not in inside
    ]
    for pack, members in sorted(grouped.items()):
        names = [s.name for s in members]
        shown = ", ".join(names[:PACK_NAMES_SHOWN]) + (
            f", and {len(names) - PACK_NAMES_SHOWN} more" if len(names) > PACK_NAMES_SHOWN else ""
        )
        lines.append(
            f"- {pack} (pack of {len(names)} skills: {shown}): load_skill('{pack}') lists them with their descriptions, "
            "or load one of them by name."
        )
    return "Skills (load one with load_skill when a task matches):\n" + "\n".join(lines)
