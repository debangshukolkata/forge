"""The spawn_subagent tool: the main agent delegates a self-contained job to a subagent with its own fresh
context. Lives in the agent module (not tools) because it starts agents; subagents never get it, so they
can't nest (spec §13B)."""

from __future__ import annotations

from forge.config import forge_home
from forge.errors import LLMError
from forge.parity.agents import load_agents
from forge.subagents.builder import (
    BUILDER_ITERATIONS,
    BUILDER_PROMPT,
    append_ledger,
    parse_status,
    report_path,
    result_text,
    safe_name,
)
from forge.subagents.code_review import run_code_review
from forge.subagents.critic import (
    CRITIC_ITERATIONS,
    CRITIC_PROMPT,
    CRITIC_ROUND_LIMIT,
    critic_round_note,
    critic_verdict,
    has_blocking_fix,
)
from forge.subagents.review import REVIEWER_PROMPT
from forge.subagents.subagent import (
    DEBUGGER_PROMPT,
    EXPLORE_PROMPT,
    PLANNER_PROMPT,
    RESEARCHER_ITERATIONS,
    RESEARCHER_PROMPT,
    VERIFIER_ITERATIONS,
    VERIFIER_PROMPT,
    _run_subagent,
)
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.toolkit.folders import clean_folder
from forge.toolkit.shell import RunCommand, ShellSession
from forge.tools.parity import BUILT_IN_TYPES
from forge.tools.registry import ToolRegistry, default_tools


async def run_builder(context: ToolContext, *, folder: str, name: str, task: str) -> tuple[str, str, str]:
    """Runs one builder to the end and returns (status, report, saved report path). Shared by `spawn_subagent` and the scheduler (X7)."""
    router = context.router
    assert router is not None
    workspace = context.workspace
    workspace.path_of(folder).mkdir(parents=True, exist_ok=True)
    # Its own shell session: the working directory belongs to the session, and two builders must not move each other's.
    shell = ShellSession(workspace)
    shell.cwd = workspace.path_of(folder)
    tools = ToolRegistry([t for t in default_tools() if t.name not in ("ask_user",)])
    brief = (
        f"Your folder: {folder}/ (you can write only there; your commands start there).\n"
        f"Your name: {name}.\n\nBRIEF:\n{task}"
    )
    report = await _run_subagent(
        router,
        context,
        tools,
        BUILDER_PROMPT,
        brief,
        BUILDER_ITERATIONS,
        "coder",
        write_only_under=folder + "/",
        needs_user_approvals=True,
        shell=shell,
        builder=True,
    )
    status = parse_status(report)
    saved = report_path(name)
    target = workspace.root / saved
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(report, encoding="utf-8")
    lines = [line for line in report.splitlines() if line.strip()]
    append_ledger(workspace.forge_dir, name, folder, status, lines[-2] if len(lines) > 1 else report)
    return status, report, saved


class SpawnSubagent(Tool):
    name = "spawn_subagent"
    read_only = True  # the subagent's own tools are restricted; only its report comes back
    description = (
        "Delegate a self-contained job to a subagent with its own fresh context: 'explore' "
        "(read-only search), 'planner' (read-only: studies the code and returns the approach, the assumptions, the task breakdown with a check for each, and the risks; use it for a "
        "large, ambiguous or many-file task before you start, not for a small change), "
        "'researcher' (digs into a question on the web, cross-checks sources, reports with URLs), "
        "'reviewer' (second opinion on a change), 'debugger' (root cause of a failure), 'verifier' "
        "(independently derives acceptance checks from the requirement, writes and runs its own "
        "Playwright or test scripts against the running app and reports PASS/FAIL), 'design-critic' "
        "(an independent designer who looks at the running page at desktop and phone width and scores "
        "its look and feel, with concrete fixes and a SHIP/REVISE verdict), or a custom agent "
        "defined by the user, 'code-review' (two independent reviewers at once, one for the project's standards and one for what was asked, with a SHIP/REVISE verdict; ask for it before you finish a code task of any size), or 'builder' (builds one self-contained piece of work in its own `folder`, writes only "
        "there, runs its own checks and ends with a STATUS line; several builders with different folders given in "
        "the same turn run in parallel: use it for independent variants, screens or services, see the parallel-builders "
        "skill). "
        "Give it everything it needs in `task`; you get its report back."
    )

    class Args(ToolArgs):
        agent: str
        task: str
        folder: str = ""  # builder only: the folder it may write below, relative to the repository root
        name: str = ""  # builder only: a short name for its report and the ledger

    def summary(self, args: SpawnSubagent.Args) -> str:
        return f"subagent {args.agent}: {args.task[:80]}"

    async def _run_builder(
        self, args: SpawnSubagent.Args, context: ToolContext, read_only: list[Tool]
    ) -> ToolResult:
        folder = clean_folder(args.folder)
        if not folder:
            return ToolResult(
                ok=False,
                content="A builder needs `folder`: the folder below the repository root it may write in (for example "
                "'designs/design-a'). Give each parallel builder its own folder.",
            )
        name = safe_name(args.name, folder)
        status, report, saved = await run_builder(context, folder=folder, name=name, task=args.task)
        return ToolResult(ok=True, content=result_text(name, folder, status, report, saved))

    async def run(self, args: SpawnSubagent.Args, context: ToolContext) -> ToolResult:
        router = context.router
        if router is None:
            return ToolResult(ok=False, content="Subagents aren't available in this context.")
        read_only = [t for t in default_tools() if t.read_only]
        if args.agent == "explore":
            report = await _run_subagent(
                router, context, ToolRegistry(read_only), EXPLORE_PROMPT, args.task, 25, "coder"
            )
        elif args.agent == "planner":
            report = await _run_subagent(
                router, context, ToolRegistry(read_only), PLANNER_PROMPT, args.task, 25, "planner"
            )
        elif args.agent == "researcher":
            try:
                report = await _run_subagent(
                    router,
                    context,
                    ToolRegistry(read_only),
                    RESEARCHER_PROMPT,
                    args.task,
                    RESEARCHER_ITERATIONS,
                    "coder",
                    needs_user_approvals=True,
                )
            except LLMError as error:  # whatever the model could not finish, the caller still gets an answer
                report = (
                    f"The researcher stopped early ({error}). Search with web_search yourself, or ask "
                    "again with "
                    "a narrower question."
                )
        elif args.agent == "debugger":
            tools = ToolRegistry([*read_only, RunCommand()])
            report = await _run_subagent(router, context, tools, DEBUGGER_PROMPT, args.task, 20, "reviewer")
        elif args.agent == "builder":
            return await self._run_builder(args, context, read_only)
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
                    "delete_file",
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
        elif args.agent == "design-critic":
            everything = {t.name: t for t in default_tools()}
            looking = [everything[n] for n in everything if n.startswith("browser_")] + [
                everything["view_image"]
            ]
            report = await _run_subagent(
                router,
                context,
                ToolRegistry([*read_only, *(t for t in looking if t not in read_only)]),
                CRITIC_PROMPT,
                args.task,
                CRITIC_ITERATIONS,
                "critic",
            )
            context.last_critic_step = context.step
            verdict = critic_verdict(report)
            if verdict == "SHIP":
                context.critic_ship, context.critic_rounds = True, 0
            elif not has_blocking_fix(report):
                # One review by default (D-360): a REVISE with only suggestions does not need a second round. The builder applies the cheap ones
                # in its closing step and reports the rest, as after the last allowed round.
                context.critic_ship, context.critic_rounds = False, CRITIC_ROUND_LIMIT
                report += (
                    "\n[The review found nothing BLOCKING, so no second review is needed. Apply the cheap suggestions in your next step (together with "
                    "anything else you have to do), say in your verification which suggestions remain open, then call task_update.]"
                )
            else:
                context.critic_ship, context.critic_rounds = False, context.critic_rounds + 1
                report += critic_round_note(verdict, context.critic_rounds, CRITIC_ROUND_LIMIT)
        elif args.agent == "code-review":
            requirement = ""
            asker = getattr(context.interaction, "requirement_text", None)
            if callable(asker):
                requirement = str(asker())
            report = await run_code_review(router, context, requirement or args.task)
            context.last_review_step = context.step
            context.review_ship = "VERDICT: SHIP" in report
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
            unknown = [n for n in custom.tools if n not in everything]
            if unknown:
                return ToolResult(
                    ok=False,
                    content=f"Agent {args.agent!r} lists unknown tools: {', '.join(unknown)}. "
                    f"Known tools: {', '.join(sorted(everything))}.",
                )
            chosen = [everything[n] for n in custom.tools] or read_only
            report = await _run_subagent(
                router,
                context,
                ToolRegistry(chosen),
                custom.prompt,
                args.task,
                custom.max_steps or 25,
                custom.role,
                write_only_under=custom.write_only_under,
            )
        return ToolResult(ok=True, content=f"[{args.agent} report]\n{report}")
