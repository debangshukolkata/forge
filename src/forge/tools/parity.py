"""Parity tools (spec §13B): load_skill (full text of a skill whose description is pinned) and spawn_subagent
(built-in types explore / reviewer / debugger, or a custom agent from <forge_home>/agents/). A subagent works
with its own context and tools and returns a report (<= ~1.5k tokens)."""

from __future__ import annotations

from typing import Any

from forge.config import forge_home
from forge.memory.scope import repo_level_dir
from forge.parity.plugins import plugin_skill_roots
from forge.parity.skills import Skill, discover, pack_listing, packs
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

BUILT_IN_TYPES = {
    "explore": "Read-only exploration of the codebase for a question; returns relevant files and conventions.",
    "planner": "Read-only analysis for a large or ambiguous task (the planner model): approach, assumptions, ordered tasks with a check each, risks.",
    "art-director": "Read-only designer (the planner model): from the brief, the reference notes and the design knowledge base returns a complete DESIGN.md with a reason for every decision.",
    "reviewer": "A second opinion on a change (reviewer model); returns findings.",
    "security-auditor": "Read-only security review (reviewer model): injection, secrets, missing access checks, unsafe file and network use; findings with evidence and a verdict.",
    "code-review": "Two independent reviewers at once, one for the project's standards and one for what was asked; returns both reports and a SHIP/REVISE verdict.",
    "debugger": "Fresh-context root-cause analysis of a failure (can run tests); returns a diagnosis and fix.",
    "researcher": "Digs into a question on the web: searches, reads several sources, cross-checks, and "
    "reports findings with source URLs, what disagrees and what could not be read.",
    "design-critic": "Independent designer: looks at the running page at desktop and phone width, scores its look "
    "and feel against a rubric and returns concrete fixes with a SHIP or REVISE verdict.",
    "verifier": "Independent acceptance check: derives checks from the requirement, writes and runs its own "
    "Playwright/test scripts against the running app, and reports PASS/FAIL per check.",
}


def skill_roots(context: ToolContext) -> list[Any]:
    roots: list[Any] = [forge_home() / "skills", *plugin_skill_roots(forge_home())]
    profile_root = context.profile.root if context.profile is not None else None
    roots.append(repo_level_dir(forge_home(), context.workspace, profile_root) / "skills")
    return roots


MAX_SKILL_FILE_BYTES = 200_000


# Folders that hold many files of one kind: listed as one line each (the catalogue tools find the assets inside).
BULK_FOLDERS = (
    "assets/",
    "fonts/",
    "templates/",
    "recipes/sections/",
    "recipes/compositions-react/",
    "recipes/templates/",
    "recipes/app-screens/",  # D-366, D-377: found with find_asset; listed one by one they pushed the reference files out of the 60 shown
    "recipes/app-react/",
    "recipes/compositions/",
    "recipes/design-systems/",
)
KEPT_FROM_BULK = {"assets/INDEX.md", "assets/README.md"}


def skill_files_note(skill: Skill) -> str:
    """Tells the model what else the skill folder holds and how to reach it."""
    others = sorted(
        p.relative_to(skill.folder).as_posix()
        for p in skill.folder.rglob("*")
        if p.is_file() and p.name != "SKILL.md" and not p.is_symlink()
    )
    if not others:
        return ""
    shown: list[str] = []
    bulk: dict[str, int] = {}
    for name in others:
        folder = next((f for f in BULK_FOLDERS if name.startswith(f)), None)
        if folder is None or name in KEPT_FROM_BULK:
            shown.append(f"- {name}")
        else:
            bulk[folder] = bulk.get(folder, 0) + 1
    shown = shown[:60] + (["- ..."] if len(shown) > 60 else [])
    shown += [
        f"- {folder} ({count} files; search the catalogue with find_asset instead of listing)"
        for folder, count in bulk.items()
    ]
    listed = "\n".join(shown)
    return (
        f"\n\n---\nThis skill's folder is {skill.folder} (you may read it, read only). Read its files with "
        "read_file or load_skill(name, file=...). A program in it runs through the shell with its full path, "
        f"for example python {skill.folder}/scripts/<name>.py, and goes through the usual approval.\n"
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
        if skill is None and not args.file and args.name.strip() in (grouped := packs(skills)):
            return ToolResult(ok=True, content=pack_listing(args.name.strip(), grouped[args.name.strip()]))
        if skill is None:
            return ToolResult(
                ok=False,
                content=(
                    f"No skill {args.name!r} is installed on this machine. "
                    f"Skills: {', '.join(sorted(skills))}. "
                    "If the user gave you its GitHub link, use install_skill; otherwise ask for the link "
                    "or tell them to run `/skill add <github link>`."
                ),
            )
        if args.file:
            return read_skill_file(skill, args.file)
        if skill.fork:
            return ToolResult(
                ok=True,
                content=(
                    f"The skill {skill.name!r} runs in a context of its own, so its long instructions and working notes stay out of this conversation. "
                    f"Call spawn_subagent with agent \"skill:{skill.name}\" and a `task` that holds everything it needs (it sees only that text, "
                    "and it can only read and search); you get its conclusion back."
                ),
            )
        if skill.own_design:
            context.design_exempt = True
        return ToolResult(ok=True, content=skill.body() + skill_files_note(skill))
