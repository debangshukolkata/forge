"""The spawn_subagent tool: the main agent delegates a self-contained job to a subagent with its own fresh
context. Lives in the agent module (not tools) because it starts agents; subagents never get it, so they
can't nest (spec §13B)."""

from __future__ import annotations

from forge.config import forge_home
from forge.parity.agents import load_agents
from forge.subagents.review import REVIEWER_PROMPT
from forge.subagents.subagent import (
    DEBUGGER_PROMPT,
    EXPLORE_PROMPT,
    VERIFIER_ITERATIONS,
    VERIFIER_PROMPT,
    _run_subagent,
)
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.toolkit.shell import RunCommand
from forge.tools.parity import BUILT_IN_TYPES
from forge.tools.registry import ToolRegistry, default_tools


class SpawnSubagent(Tool):
    name = "spawn_subagent"
    read_only = True  # the subagent's own tools are restricted; only its report comes back
    description = (
        "Delegate a self-contained job to a subagent with its own fresh context: 'explore' "
        "(read-only search), "
        "'reviewer' (second opinion on a change), 'debugger' (root cause of a failure), 'verifier' "
        "(independently derives acceptance checks from the requirement, writes and runs its own "
        "Playwright or test scripts against the running app and reports PASS/FAIL), or a custom agent "
        "defined by the user. "
        "Give it everything it needs in `task`; you get its report back."
    )

    class Args(ToolArgs):
        agent: str
        task: str

    def summary(self, args: SpawnSubagent.Args) -> str:
        return f"subagent {args.agent}: {args.task[:80]}"

    async def run(self, args: SpawnSubagent.Args, context: ToolContext) -> ToolResult:
        router = context.router
        if router is None:
            return ToolResult(ok=False, content="Subagents aren't available in this context.")
        read_only = [t for t in default_tools() if t.read_only]
        if args.agent == "explore":
            report = await _run_subagent(
                router, context, ToolRegistry(read_only), EXPLORE_PROMPT, args.task, 25, "coder"
            )
        elif args.agent == "debugger":
            tools = ToolRegistry([*read_only, RunCommand()])
            report = await _run_subagent(router, context, tools, DEBUGGER_PROMPT, args.task, 20, "reviewer")
        elif args.agent == "verifier":
            everything = {t.name: t for t in default_tools()}
            wanted = [
                n
                for n in everything
                if n.startswith("browser_")
                or n
                in (
                    "write_file",
                    "edit_file",
                    "run_command",
                    "python_run",
                    "start_background",
                    "read_background",
                    "stop_background",
                    "http_request",
                    "view_image",
                )
            ]
            tools = ToolRegistry(
                [*read_only, *(everything[n] for n in wanted if everything[n] not in read_only)]
            )
            report = await _run_subagent(
                router,
                context,
                tools,
                VERIFIER_PROMPT,
                args.task,
                VERIFIER_ITERATIONS,
                "coder",
                write_only_under="tests/e2e/",
                needs_user_approvals=True,
            )
            if "VERDICT: PASS" in report:
                context.last_browser_step = context.step  # an independent browser check passed (D-167/D-168)
        elif args.agent == "reviewer":
            report = await _run_subagent(
                router, context, ToolRegistry(read_only), REVIEWER_PROMPT, args.task, 20, "reviewer"
            )
        else:
            custom = load_agents(forge_home()).get(args.agent)
            if custom is None:
                names = ", ".join([*BUILT_IN_TYPES, *load_agents(forge_home())])
                return ToolResult(ok=False, content=f"No agent {args.agent!r}. Agents: {names}")
            everything = {t.name: t for t in default_tools()}
            chosen = [everything[n] for n in custom.tools if n in everything] or read_only
            report = await _run_subagent(
                router, context, ToolRegistry(chosen), custom.prompt, args.task, 25, custom.role
            )
        return ToolResult(ok=True, content=f"[{args.agent} report]\n{report}")
