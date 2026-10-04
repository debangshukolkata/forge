"""Parity tools (spec §13B): load_skill (full text of a skill whose description is pinned) and spawn_subagent
(built-in types explore / reviewer / debugger, or a custom agent from <forge_home>/agents/). A subagent works
with its own context and tools and returns a report (<= ~1.5k tokens)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from forge.config import forge_home
from forge.memory.scope import repo_level_dir
from forge.parity.skills import Skill, discover
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.workspace.workspace import Workspace

BUILT_IN_TYPES = {
    "explore": "Read-only exploration of the codebase for a question; returns relevant files and "
    "conventions.",
    "reviewer": "A second opinion on a change (reviewer model); returns findings.",
    "debugger": "Fresh-context root-cause analysis of a failure (can run tests); returns a "
    "diagnosis and fix.",
    "verifier": "Independent acceptance check: derives checks from the requirement, writes and runs its own "
    "Playwright/test scripts against the running app, and reports PASS/FAIL per check.",
}


def skill_roots(context: ToolContext) -> list[Any]:
    roots: list[Any] = [forge_home() / "skills"]
    profile_root = context.profile.root if context.profile is not None else None
    roots.append(repo_level_dir(forge_home(), context.workspace, profile_root) / "skills")
    return roots


MAX_SKILL_FILE_BYTES = 200_000


def stage_skill(skill: Skill, workspace: Workspace) -> Path:
    """Copies the skill's folder into <code folder>/.forge/skills. Mode B never runs or reads anything outside
    its code folder, so a skill's scripts and data are only usable from a copy inside it; .forge/ is never
    delivered (workspace/ignore.py)."""
    destination = workspace.jail.check(workspace.repo_dir / ".forge" / "skills" / skill.name)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(skill.folder, destination, symlinks=False, ignore_dangling_symlinks=True)
    return destination


def skill_files_note(skill: Skill, staged: Path) -> str:
    """Tells the model what else the skill folder holds and how to reach it."""
    others = sorted(
        p.relative_to(skill.folder).as_posix()
        for p in skill.folder.rglob("*")
        if p.is_file() and p.name != "SKILL.md" and not p.is_symlink()
    )
    if not others:
        return ""
    listed = "\n".join(f"- {name}" for name in others[:60]) + ("\n- ..." if len(others) > 60 else "")
    return (
        f"\n\n---\nForge copied this skill's folder into the project: {staged}\n"
        "Read its files with read_file or load_skill(name, file=...). Run its programs by this full path "
        f"(for example python {staged}/scripts/<name>.py); they go through the usual approval.\n"
        f"Files:\n{listed}"
    )


def read_skill_file(skill: Skill, relative: str) -> ToolResult:
    root = skill.folder.resolve()
    target = (root / relative).resolve()
    if root not in target.parents or not target.is_file() or (root / relative).is_symlink():
        return ToolResult(ok=False, content=f"{relative!r} is not a file inside the skill folder.")
    if target.stat().st_size > MAX_SKILL_FILE_BYTES:
        return ToolResult(ok=False, content=f"{relative!r} is larger than {MAX_SKILL_FILE_BYTES // 1000} KB.")
    try:
        return ToolResult(ok=True, content=target.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return ToolResult(ok=False, content=f"{relative!r} is not a text file.")


class LoadSkill(Tool):
    name = "load_skill"
    read_only = True
    description = "Load the full instructions of a skill listed in the pinned skills index."

    class Args(ToolArgs):
        name: str
        file: str | None = (
            None  # a file inside the skill's own folder (listed in the skill's text), not SKILL.md
        )

    async def run(self, args: LoadSkill.Args, context: ToolContext) -> ToolResult:
        skills = discover(*skill_roots(context))
        skill = skills.get(args.name.strip())
        if skill is None:
            return ToolResult(
                ok=False, content=f"No skill {args.name!r}. Skills: {', '.join(sorted(skills))}"
            )
        if args.file:
            return read_skill_file(skill, args.file)
        staged = stage_skill(skill, context.workspace)
        return ToolResult(ok=True, content=skill.body() + skill_files_note(skill, staged))
