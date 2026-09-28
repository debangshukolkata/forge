"""Parity tools (spec §13B): load_skill (full text of a skill whose description is pinned) and spawn_subagent
(built-in types explore / reviewer / debugger, or a custom agent from <forge_home>/agents/). A subagent works
with its own context and tools and returns a report (<= ~1.5k tokens)."""

from __future__ import annotations

from typing import Any

from forge.config import forge_home
from forge.parity.agents import load_agents
from forge.parity.skills import discover
from forge.tools.base import Tool, ToolArgs, ToolContext, ToolResult

BUILT_IN_TYPES = {
    "explore": "Read-only exploration of the codebase for a question; returns relevant files and "
    "conventions.",
    "reviewer": "A second opinion on a change (reviewer model); returns findings.",
    "debugger": "Fresh-context root-cause analysis of a failure (can run tests); returns a "
    "diagnosis and fix.",
}


def skill_roots(context: ToolContext) -> list[Any]:
    roots: list[Any] = [forge_home() / "skills"]
    if context.kb is not None:
        roots.append(context.kb.kb_dir / "skills")
    if context.profile is not None:
        roots.append(context.profile.root / "skills")
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


class SpawnSubagent(Tool):
    name = "spawn_subagent"
    read_only = True  # the subagent's own tools are restricted; only its report comes back
    description = (
        "Delegate a self-contained job to a subagent with its own fresh context: 'explore' "
        "(read-only search), "
        "'reviewer' (second opinion on a change), 'debugger' (root cause of a failure), or a custom agent "
        "defined by the user. Give it everything it needs in `task`; you get its report back."
    )

    class Args(ToolArgs):
        agent: str
        task: str

    def summary(self, args: SpawnSubagent.Args) -> str:
        return f"subagent {args.agent}: {args.task[:80]}"

    async def run(self, args: SpawnSubagent.Args, context: ToolContext) -> ToolResult:
        from forge.agent.subagent import DEBUGGER_PROMPT, EXPLORE_PROMPT, _run_subagent
        from forge.tools.registry import ToolRegistry, default_tools
        from forge.tools.verify import RunTests, Verify

        router = context.router
        if router is None:
            return ToolResult(ok=False, content="Subagents aren't available in this context.")
        read_only = [t for t in default_tools() if t.read_only and t.name != "spawn_subagent"]
        if args.agent == "explore":
            report = await _run_subagent(
                router, context, ToolRegistry(read_only), EXPLORE_PROMPT, args.task, 25, "coder"
            )
        elif args.agent == "debugger":
            tools = ToolRegistry([*read_only, RunTests(), Verify()])
            report = await _run_subagent(router, context, tools, DEBUGGER_PROMPT, args.task, 20, "reviewer")
        elif args.agent == "reviewer":
            from forge.agent.review import REVIEWER_PROMPT

            report = await _run_subagent(
                router, context, ToolRegistry(read_only), REVIEWER_PROMPT, args.task, 20, "reviewer"
            )
        else:
            custom = load_agents(forge_home()).get(args.agent)
            if custom is None:
                names = ", ".join([*BUILT_IN_TYPES, *load_agents(forge_home())])
                return ToolResult(ok=False, content=f"No agent {args.agent!r}. Agents: {names}")
            everything = {t.name: t for t in default_tools() if t.name != "spawn_subagent"}
            chosen = [everything[n] for n in custom.tools if n in everything] or read_only
            report = await _run_subagent(
                router, context, ToolRegistry(chosen), custom.prompt, args.task, 25, custom.role
            )
        return ToolResult(ok=True, content=f"[{args.agent} report]\n{report}")
