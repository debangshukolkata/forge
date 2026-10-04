"""Planning and interaction tools (spec §9.4, D-128): ask_user, propose_requirements, propose_plan,
task_update, update_plan, request_user_action. They talk to the orchestrator through the Interaction
protocol. propose_requirements/propose_plan are optional records, not approval gates — Forge calls them
when it judges a written-down requirement or plan is worth having, not on every turn."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import Field

from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult


class OptionSpec(ToolArgs):
    label: str
    description: str = ""
    pros: str = ""
    cons: str = ""
    risks: str = ""


class TaskSpec(ToolArgs):
    id: str = Field(description="Short id, e.g. T1")
    title: str
    description: str = ""
    acceptance: str = Field(
        default="", description="The check that proves it is done (e.g. which tests pass)."
    )
    depends_on: list[str] = Field(default_factory=list)


class Interaction(Protocol):
    async def ask_user(
        self, question: str, context: str, options: list[OptionSpec], recommended: str | None
    ) -> str: ...

    async def propose_requirements(self, markdown: str) -> ToolResult: ...

    async def propose_plan(self, markdown: str, tasks: list[TaskSpec]) -> ToolResult: ...

    async def update_plan(self, markdown: str, tasks: list[TaskSpec], reason: str) -> ToolResult: ...

    async def task_update(
        self,
        task_id: str,
        status: str,
        handoff_note: str,
        verification: str,
        blocked_reason: str,
        context: ToolContext,
    ) -> ToolResult: ...

    async def request_user_action(
        self, title: str, steps: list[str], verify_command: str | None, context: ToolContext
    ) -> ToolResult: ...


def _interaction(context: ToolContext) -> Interaction | None:
    return context.interaction  # type: ignore[no-any-return]


NOT_AVAILABLE = ToolResult(
    ok=False, content="This tool is only available in an orchestrated workspace session."
)


class AskUser(Tool):
    name = "ask_user"
    read_only = True  # asking changes nothing; it waits for the user
    description = (
        "Ask the user a question. Use this, not plain text, whenever you need the user's decision or "
        "information: a design choice, a new dependency, a DB or config change, a change to shared code, "
        "or something you cannot find out yourself. It shows 2-4 clickable options (plus a box for their own "
        "answer); give each a short description, add pros/cons/risks where they matter, and recommend one. "
        "Returns the user's choice (or their own answer). Don't use it for trivia you can decide."
    )

    class Args(ToolArgs):
        question: str
        context: str = Field(default="", description="2-3 lines of background.")
        options: list[OptionSpec] = Field(min_length=2, max_length=4)
        recommended: str | None = Field(default=None, description="Label of the recommended option.")

    def summary(self, args: AskUser.Args) -> str:
        return f"ask: {args.question}"

    async def run(self, args: AskUser.Args, context: ToolContext) -> ToolResult:
        interaction = _interaction(context)
        asker = interaction.ask_user if interaction is not None else context.ask_user
        if asker is None:
            return NOT_AVAILABLE
        answer = await asker(args.question, args.context, args.options, args.recommended)
        return ToolResult(ok=True, content=answer)


class ProposeRequirements(Tool):
    name = "propose_requirements"
    read_only = True
    description = (
        "Write REQUIREMENTS.md for the record: scope, endpoints/data, acceptance criteria, edge cases, out "
        "of scope. Optional — use it for a larger requirement or when the user asks to see one; it doesn't "
        "block you from proceeding."
    )

    class Args(ToolArgs):
        markdown: str

    def summary(self, args: ProposeRequirements.Args) -> str:
        return "propose requirements"

    async def run(self, args: ProposeRequirements.Args, context: ToolContext) -> ToolResult:
        interaction = _interaction(context)
        return await interaction.propose_requirements(args.markdown) if interaction else NOT_AVAILABLE


class ProposePlan(Tool):
    name = "propose_plan"
    read_only = True
    description = (
        "Write PLAN.md and set the task list. Not an approval gate — call it when you're ready to break the "
        "work into small, independently verifiable tasks, whether or not you wrote a plan down first. The "
        "plan, if you write one, names every file to add or change (with the existing file each new file "
        "mirrors), endpoints, DB changes, tests, risks and anything the user must do."
    )

    class Args(ToolArgs):
        markdown: str
        tasks: list[TaskSpec] = Field(min_length=1)

    def summary(self, args: ProposePlan.Args) -> str:
        return f"propose plan ({len(args.tasks)} tasks)"

    async def run(self, args: ProposePlan.Args, context: ToolContext) -> ToolResult:
        interaction = _interaction(context)
        return await interaction.propose_plan(args.markdown, args.tasks) if interaction else NOT_AVAILABLE


class UpdatePlan(Tool):
    name = "update_plan"
    read_only = True
    description = "Change the approved plan (e.g. an assumption turned out wrong). Needs the user's approval."

    class Args(ToolArgs):
        markdown: str
        tasks: list[TaskSpec] = Field(
            min_length=1, description="The full task list; done tasks keep their status."
        )
        reason: str

    async def run(self, args: UpdatePlan.Args, context: ToolContext) -> ToolResult:
        interaction = _interaction(context)
        return (
            await interaction.update_plan(args.markdown, args.tasks, args.reason)
            if interaction
            else NOT_AVAILABLE
        )


class TaskUpdate(Tool):
    name = "task_update"
    read_only = True
    description = (
        "Finish the current task: status 'done' (only after a passing test/verification run AFTER your last "
        "edit — it is checked) or 'blocked' with the reason. Include a short handoff note for the next task."
    )

    class Args(ToolArgs):
        task_id: str
        status: Literal["done", "blocked"]
        handoff_note: str = Field(default="", description="<= 3 sentences the next task needs to know.")
        verification: str = Field(
            default="", description="What you ran that proves it works, and the result."
        )
        blocked_reason: str = ""

    def summary(self, args: TaskUpdate.Args) -> str:
        return f"task {args.task_id} -> {args.status}"

    async def run(self, args: TaskUpdate.Args, context: ToolContext) -> ToolResult:
        interaction = _interaction(context)
        if interaction is None:
            return NOT_AVAILABLE
        return await interaction.task_update(
            args.task_id, args.status, args.handoff_note, args.verification, args.blocked_reason, context
        )


class RequestUserAction(Tool):
    name = "request_user_action"
    read_only = True
    description = (
        "Ask the user to do something you can't (grant a DB privilege, set an env var, install a program "
        "outside the workspace, run a command you lack access for). Do not use it for anything you can run "
        "yourself: installing a package into the workspace's own virtual environment is yours to do with "
        "run_command (the user is asked to approve it); hand it to the user only if that was refused or "
        "failed. "
        "Give exact PowerShell steps and, if possible, a command that verifies it. "
        "The user answers done / skip / can't; on can't, propose a workaround or code change."
    )

    class Args(ToolArgs):
        title: str
        steps: list[str] = Field(min_length=1)
        verify_command: str | None = None

    def summary(self, args: RequestUserAction.Args) -> str:
        return f"user action: {args.title}"

    async def run(self, args: RequestUserAction.Args, context: ToolContext) -> ToolResult:
        interaction = _interaction(context)
        if interaction is None:
            return NOT_AVAILABLE
        return await interaction.request_user_action(args.title, args.steps, args.verify_command, context)
