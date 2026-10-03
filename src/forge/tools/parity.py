"""Parity tools (spec §13B): load_skill (full text of a skill whose description is pinned) and spawn_subagent
(built-in types explore / reviewer / debugger, or a custom agent from <forge_home>/agents/). A subagent works
with its own context and tools and returns a report (<= ~1.5k tokens)."""

from __future__ import annotations

from typing import Any

from forge.config import forge_home
from forge.memory.scope import repo_level_dir
from forge.parity.skills import discover
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

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


class LoadSkill(Tool):
    name = "load_skill"
    read_only = True
    description = "Load the full instructions of a skill listed in the pinned skills index."

    class Args(ToolArgs):
        name: str

    async def run(self, args: LoadSkill.Args, context: ToolContext) -> ToolResult:
        skills = discover(*skill_roots(context))
        skill = skills.get(args.name.strip())
        if skill is None:
            return ToolResult(
                ok=False, content=f"No skill {args.name!r}. Skills: {', '.join(sorted(skills))}"
            )
        return ToolResult(ok=True, content=skill.body())
