"""Planning and interaction tools (spec §9.4, D-128): ask_user, propose_requirements, propose_plan,
task_update, update_plan, request_user_action. They talk to the orchestrator through the Interaction
protocol. propose_requirements/propose_plan are optional records, not approval gates — DebCraft calls them
when it judges a written-down requirement or plan is worth having, not on every turn."""

from __future__ import annotations

import re
from typing import Literal, Protocol

from pydantic import Field

from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult


class OptionSpec(ToolArgs):
    label: str
    description: str = ""
    pros: str = ""
    cons: str = ""
    risks: str = ""
    image: str = Field(
        default="",
        description="A picture to show with the option: a PNG, JPG or WEBP path inside the project, e.g. .forge/candidates/specimen-a.png",
    )


class TaskSpec(ToolArgs):
    id: str = Field(description="Short id, e.g. T1")
    title: str
    description: str = ""
    acceptance: str = Field(
        default="", description="The check that proves it is done (e.g. which tests pass)."
    )
    depends_on: list[str] = Field(default_factory=list)
    folder: str = Field(
        default="",
        description="Where this task writes, relative to the repository root (e.g. designs/design-a). Give it to tasks that can "
        "run at the same time as others: independent tasks with separate folders are built in parallel (run_ready_tasks).",
    )
    resources: list[str] = Field(
        default_factory=list,
        description="Exclusive things the task needs (a fixed port, the database schema, a root package.json): two tasks naming "
        "the same one never run together.",
    )


class Interaction(Protocol):
    async def ask_user(
        self, question: str, context: str, options: list[OptionSpec], recommended: str | None
    ) -> str: ...

    async def propose_requirements(self, markdown: str) -> ToolResult: ...

    async def propose_plan(self, markdown: str, tasks: list[TaskSpec]) -> ToolResult: ...

    async def run_ready_tasks(self, task_ids: list[str], notes: dict[str, str]) -> ToolResult: ...

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


# Seen on the office laptop: the model asked for a JWT "in your next message", the chat masked it (as it
# must), and the model asked again, three times, with nowhere for the user to put the token. The question is
# stopped here, in the tool, and the model is sent to the route that works.
_SECRET_WORD = re.compile(r"(?i)\b(?:tokens?|jwts?|passwords?|secrets?|api[ _-]?keys?|credentials?)\b")
_PASTE = re.compile(r"(?i)\b(?:paste|pasting|re-?send|re-?enter)\b")
_GIVE = re.compile(r"(?i)\b(?:send|type|enter|provide|share|give|reply with|write)\b")
_CHAT = re.compile(r"(?i)\b(?:chat|messages?|here|below|me)\b")
# "Add the line to the .env file; do not paste the token into the chat" is the right question, not the wrong one.
_NOT = re.compile(r"(?i)\b(?:do not|don't|never|not|without|instead of)\b")
SECRET_IN_CHAT = (
    "Not asked: this asks the user to put a secret into the chat. Anything secret typed there is replaced by "
    "[REDACTED] before you see it, by design, so the answer could never reach you and asking again cannot "
    "help. Use the route that works: for a command you run (a script, a test, the application itself), call "
    "request_app_secret with the NAMES of the variables (for example ARGOCD_TOKEN): the user keeps the values in "
    "DebCraft's .env file and your commands get them as environment variables. For a call to the application's "
    "API on localhost, call http_request with `token_env`. If your question is about how the product you are "
    "building should handle secrets, ask it again without telling the user to paste or send one."
)


# Also seen there (D-570): "Restart DebCraft so this session inherits DEVELOPMENT_INSTANCE_TOKEN", "set the
# variable in the environment DebCraft commands inherit from". Neither is ever needed: the .env file is read on
# every call, and request_app_secret hands its values to commands.
_RESTART = re.compile(
    r"(?i)\b(?:re-?start|reload|relaunch|re-?open|close)\b[^.\n]{0,60}\b(?:debcraft|forge|session)\b"
    r"|\b(?:new|fresh)\s+(?:debcraft\s+)?(?:session|one)\b[^.\n]{0,80}\b(?:env|token|variable)"
)
_INHERIT = re.compile(
    r"(?i)\b(?:inherits?|visible to|visible environment|available to|loaded into|can read it)\b"
    r"[^.\n]{0,80}\b(?:debcraft|session|commands?|token|variables?|env)\b"
    r"|\b(?:debcraft|session|commands?)\b[^.\n]{0,60}\b(?:inherits?|can read)\b"
)
ENV_NEEDS_NO_STEP = (
    "Not asked: this sends the user to restart DebCraft or to put a variable where DebCraft or its commands "
    "can see it. Neither is ever needed. DebCraft reads its .env file again on every call, so a value the user "
    "has saved there is usable now. What you saw as missing in a command is by design: commands do not inherit "
    "DebCraft's variables. Do it yourself instead: call request_app_secret with the names (the user confirms "
    "with one click and edits nothing) and run the command again; for a call to the application's API on "
    "localhost call http_request with `token_env` (it also tries the token with and without `Bearer`). Ask the "
    "user only for a value that is really not in the file, through request_app_secret, which shows them the "
    "line to add."
)


def asks_for_a_restart_or_copy(texts: list[str]) -> bool:
    """True when the user is told to restart DebCraft or to make a variable visible to it."""
    return any(_RESTART.search(text) or _INHERIT.search(text) for text in texts)


def asks_for_a_secret_in_chat(texts: list[str]) -> bool:
    """True when a sentence of the question or an option tells the user to paste or send a secret in the chat."""
    for text in texts:
        named_before = False  # "I need the token. Send it here.": the secret is named one sentence earlier
        for sentence in re.split(r"(?<=[.?!])\s+|\n", text):
            named = bool(_SECRET_WORD.search(sentence))
            if not (named or named_before):
                continue
            named_before = named
            verb = _PASTE.search(sentence) or (_CHAT.search(sentence) and _GIVE.search(sentence))
            if verb and not _NOT.search(sentence[: verb.start()]):
                return True
    return False


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
        texts = [args.question, args.context]
        texts += [f"{option.label}. {option.description}" for option in args.options]
        if asks_for_a_secret_in_chat(texts):
            return ToolResult(ok=False, content=SECRET_IN_CHAT)
        if asks_for_a_restart_or_copy(texts):
            return ToolResult(ok=False, content=ENV_NEEDS_NO_STEP)
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


class RunReadyTasks(Tool):
    name = "run_ready_tasks"
    read_only = True
    description = (
        "Build the planned tasks that can run at the same time: the pending tasks whose dependencies are done, that name a "
        "`folder` of their own and share no folder or resource with each other, each by its own builder in parallel (at most "
        "limits.max_parallel_builders). You get every builder's report and status back; then verify the results yourself "
        "(tests, a look at the page) before task_update(done). If nothing can run in parallel it says why: then work on the "
        "next task yourself. Load the parallel-builders skill first."
    )

    class Args(ToolArgs):
        task_ids: list[str] = Field(
            default_factory=list, description="Only these tasks; empty = every task that can run now."
        )
        notes: dict[str, str] = Field(
            default_factory=dict,
            description="Extra facts for a builder by task id (names, numbers, interfaces to follow).",
        )

    async def run(self, args: RunReadyTasks.Args, context: ToolContext) -> ToolResult:
        interaction = _interaction(context)
        return await interaction.run_ready_tasks(args.task_ids, args.notes) if interaction else NOT_AVAILABLE


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
        "Ask the user to do something you can't (grant a DB privilege, change a Windows setting, install a program "
        "outside the workspace, run a command you lack access for). Do not use it for anything you can run "
        "yourself: installing a package into the workspace's own virtual environment is yours to do with "
        "run_command (the user is asked to approve it); hand it to the user only if that was refused or "
        "failed. "
        "Give exact PowerShell steps and, if possible, a command that verifies it. "
        "The user answers done / skip / can't; on can't, propose a workaround or code change. "
        "Never for a value of DebCraft's .env file, a secret or a restart of DebCraft: the file is read on every "
        "call and request_app_secret hands its values to your commands."
    )

    class Args(ToolArgs):
        title: str
        steps: list[str] = Field(min_length=1)
        verify_command: str | None = None

    def summary(self, args: RequestUserAction.Args) -> str:
        return f"user action: {args.title}"

    async def run(self, args: RequestUserAction.Args, context: ToolContext) -> ToolResult:
        texts = [args.title, *args.steps]
        if asks_for_a_secret_in_chat(texts):
            return ToolResult(ok=False, content=SECRET_IN_CHAT)
        if asks_for_a_restart_or_copy(texts):
            return ToolResult(ok=False, content=ENV_NEEDS_NO_STEP)
        interaction = _interaction(context)
        if interaction is None:
            return NOT_AVAILABLE
        from forge.tools.handoff_review import review_hand_off  # here: that module imports this one

        sent_back = await review_hand_off(args.title, args.steps, args.verify_command, context)
        if sent_back:
            return ToolResult(ok=False, content=sent_back)
        return await interaction.request_user_action(args.title, args.steps, args.verify_command, context)
