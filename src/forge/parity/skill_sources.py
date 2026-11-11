"""Known skill sources (D-562): skills DebCraft may download from GitHub when a task needs one.

The skills themselves are not part of DebCraft; only a short list of links is (`defaults/skill_sources.yaml`),
which the user extends or changes in `<DebCraft Home>/skill_sources.yaml`. A listed skill that is not on the
machine yet is shown in the skills index as available; `load_skill` downloads it after the user approves once,
and from then on it is an installed skill like any other. The model can never add to this list: both files
are outside every workspace, so the write jail keeps them out of its reach.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError

from forge.parity.skills import Skill

SOURCES_FILE = "skill_sources.yaml"
BROWSER_NOTE = (
    "A script of this skill that starts Chrome or Edge itself cannot run inside DebCraft's command sandbox "
    "(it ends with a DevTools pipe error that says nothing about the page). Do not retry it: look at the page "
    "with browser_open and browser_screenshot instead, and say which of the skill's own checks you could not run."
)


class SkillSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    source: str
    use_when: str = ""
    needs: str = ""
    tools: list[str] = []
    own_design: bool = False
    enabled: bool = True


def _read(path: Path) -> tuple[list[SkillSource], list[str]]:
    """The valid entries of one file and a line per entry or file that could not be read."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        return [], [f"{path.name}: {error}"]
    rows = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        return [], [f"{path.name}: expected a `sources:` list"]
    found: list[SkillSource] = []
    problems: list[str] = []
    for row in rows:
        try:
            found.append(SkillSource.model_validate(row))
        except ValidationError as error:
            problems.append(f"{path.name}: {error.errors()[0]['loc']} {error.errors()[0]['msg']}")
    return found, problems


def load_sources(home: Path) -> tuple[dict[str, SkillSource], list[str]]:
    """Every enabled source by skill name: the built-in list, then the user's file on top of it."""
    builtin = Path(str(resources.files("forge") / "defaults" / SOURCES_FILE))
    merged: dict[str, SkillSource] = {}
    problems: list[str] = []
    for path in (builtin, home / SOURCES_FILE):
        if not path.is_file():
            continue
        entries, bad = _read(path)
        problems += bad
        merged.update({entry.name: entry for entry in entries})
    return {name: entry for name, entry in merged.items() if entry.enabled}, problems


def available(home: Path, installed: dict[str, Skill]) -> dict[str, SkillSource]:
    """The listed skills that are not on this machine yet."""
    sources, _ = load_sources(home)
    return {name: entry for name, entry in sources.items() if name not in installed}


def index_lines(waiting: dict[str, SkillSource]) -> str:
    """The part of the skills index that lists what can be downloaded."""
    if not waiting:
        return ""
    lines = [f"- {entry.name}: {entry.use_when or 'see its source'}" for entry in waiting.values()]
    return (
        "Skills not on this machine yet (load_skill(name) downloads one from GitHub after the user approves "
        "once; then it stays installed). Pick one only when the task calls for it:\n" + "\n".join(lines)
    )


def loading_note(entry: SkillSource) -> str:
    """What DebCraft adds below a listed skill's own text when it is loaded."""
    parts = [f"Needs: {entry.needs}"] if entry.needs else []
    if "Chrome" in entry.needs or "browser" in entry.needs:
        parts.append(BROWSER_NOTE)
    if entry.own_design:
        parts.append(
            "This skill sets the look of the page: follow it instead of the ui-design-quality skill, and do "
            "not load a second design skill for the same task."
        )
    return ("\n\n[DebCraft note on this skill]\n" + "\n".join(parts)) if parts else ""
