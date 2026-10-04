"""Runs one agent session: consumes user inputs, calls the LLM, publishes events.

With a workspace attached, each turn runs the tool-using agent loop (agent/loop.py); without one it
is a plain chat. Phases and approvals of plans arrive with the orchestrator (M6).
"""

from __future__ import annotations

import asyncio
import contextlib
import traceback
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg

from forge.agent.loop import AgentLoop, system_prompt
from forge.config import Secrets, forge_home, permission_rules
from forge.context.manager import ContextManager
from forge.db.access import AccessLevel
from forge.db.credential_tables import credential_tables
from forge.db.scratch import ScratchError
from forge.db.session import DbSession
from forge.engine.slash_commands import SlashCommandHandler
from forge.environment.store import tavily_declined, tesseract_ready
from forge.errors import BudgetExceededError, ConfigError, LLMError
from forge.llm.base import ChatRequest, Message
from forge.llm.router import LLMRouter
from forge.llm.usage_ledger import UsageLedger
from forge.memory.scope import repo_level_dir, scope_of
from forge.memory.store import combined_index
from forge.modeb.profile import HostProfile, ProfileError, ProfileStore, host_identifying_terms
from forge.modeb.workspace import profile_ref
from forge.parity.history import History
from forge.parity.instructions import InstructionFile, instruction_files
from forge.parity.instructions import append_line as append_instruction
from forge.parity.instructions import render as render_instructions
from forge.parity.mcp_client import McpHub
from forge.parity.mentions import expand as expand_mentions
from forge.parity.skills import discover
from forge.parity.skills import index_text as skills_index
from forge.protocol.approvals import ApprovalBroker, QuestionBroker
from forge.protocol.events import EventBus, EventType
from forge.protocol.inputs import Answer, Approve, Interrupt, Reject, SendMessage, SlashCommand, UserInput
from forge.safety.permissions import PermissionGate, PermissionMode
from forge.safety.redact import default_redactor
from forge.subagents.spawn_tool import SpawnSubagent
from forge.toolkit.background import BackgroundManager
from forge.toolkit.base import Tool, ToolContext
from forge.toolkit.shell import ShellSession, execute
from forge.tools.interaction import AskUser
from forge.tools.modeb import modeb_tools
from forge.tools.registry import ToolRegistry, db_tools, default_tools
from forge.tools.todo import PIN_SLOT as TODO_PIN_SLOT
from forge.tools.todo import TodoItem
from forge.tools.todo import render as render_todos
from forge.tools.vision import ocr_tools
from forge.tools.web import azure_hosted_search
from forge.tools.web_guard import WebPolicy
from forge.workflow.orchestrator import Orchestrator
from forge.workspace.read_grants import ReadGrants
from forge.workspace.workspace import Workspace

DEFAULT_SYSTEM_PROMPT = (
    "You are Forge, a software engineering assistant running on the user's Windows laptop. "
    "Be concise and precise. If you are not sure about something, say so."
)


class SessionHost:
    def __init__(
        self,
        router: LLMRouter,
        bus: EventBus,
        system_prompt_text: str | None = None,
        workspace: Workspace | None = None,
        permission_mode: PermissionMode | None = None,
        orchestrated: bool = False,
        secrets: Secrets | None = None,
    ) -> None:
        self.router = router
        self.bus = bus
        self.workspace = workspace
        if workspace is not None:
            workspace.read_grants = ReadGrants.for_workspace(workspace.root, forge_home())
        self.secrets = secrets
        self.approvals = ApprovalBroker(bus)
        self.questions = QuestionBroker(bus)
        self.context_manager = self._build_context_manager(workspace)
        self.agent: AgentLoop | None = None
        if workspace is not None:
            self.agent = self._build_agent(workspace, permission_mode or router.config.shell.permission_mode)
        self.system_prompt = system_prompt_text or (
            system_prompt(workspace) if workspace is not None else DEFAULT_SYSTEM_PROMPT
        )
        self.history: list[Message] = [Message.system(self.system_prompt)]
        self._inputs: asyncio.Queue[UserInput] = asyncio.Queue()
        self._current_turn: asyncio.Task[None] | None = None
        self._streamed: list[str] = []
        self._commands = SlashCommandHandler(self)
        self.closed = False
        # Orchestrated sessions run the requirement workflow (spec §7); otherwise messages go straight to
        # the tool-using agent ("direct" mode).
        self.orchestrator: Orchestrator | None = Orchestrator(self) if orchestrated and self.agent else None
        if self.workspace is not None:  # tokens and cost per phase and task of this project (D-118)
            self.router.cost.ledger = UsageLedger(
                self.workspace.jail.check(self.workspace.forge_dir / "usage.json")
            )
            self.router.cost.where = self._usage_where
        if self.orchestrator is not None:  # every event says which task it belongs to (usage ledger)
            self.bus.stamp = lambda: dict(zip(("phase", "task"), self._usage_where(), strict=True))
        if workspace is not None:
            self.refresh_instructions()

    def refresh_profile_pin(self) -> None:
        """Mode B: the host profile's essentials, plus active interface contracts (§6A.2A, D-129), are pinned.
        Mode A pins nothing: Forge reads the repository itself (D-160)."""
        profile = self.host_profile()
        essentials: str | None = None
        if profile is not None:
            from forge.modeb.contracts import ContractRegister

            contracts = ContractRegister(profile).essentials()
            essentials = profile.essentials() + (f"\n\n{contracts}" if contracts else "")
        self.context_manager.pinned.set("kb_essentials", essentials)

    def host_profile(self) -> HostProfile | None:
        """Mode B: the profile this workspace uses (spec §6A.2)."""
        if self.workspace is None or not self.workspace.mode_b:
            return None
        name = profile_ref(self.workspace).get("profile")
        try:
            return ProfileStore(forge_home()).open(str(name))
        except ProfileError:
            return None

    @property
    def db(self) -> DbSession | None:
        return self.agent.context.db if self.agent is not None else None

    def _build_db(self, workspace: Workspace) -> DbSession | None:
        settings = self.router.config.postgres
        if self.secrets is None or not any(
            self.secrets.get(c.url_env) for c in settings.connections.values()
        ):
            return None
        tables = (
            []
            if workspace.mode_b
            else credential_tables(workspace.info.repo_path, workspace.info.app_subfolder)
        )
        return DbSession(settings, self.secrets, workspace, forge_home(), tables)

    async def prepare_database(self, force: bool = False) -> None:
        """Spec §9.5.2 at the start of work: access level per database, then the scratch schema (created
        by Forge only when its role may and config allows; otherwise the agent writes a DB request)."""
        db = self.db
        if db is None or (db.reports and not force):
            return
        await asyncio.to_thread(db.detect)
        target = db.preferred_target()
        if target is not None:
            report = db.reports[target]
            try:
                scratch = db.activate_scratch(target)
                if (
                    not report.scratch_exists
                    and self.router.config.postgres.scratch.create == "forge_if_allowed"
                ):
                    await asyncio.to_thread(scratch.create_schema)
                    report.scratch_exists = True
            except (psycopg.Error, ScratchError, OSError) as error:
                db.scratch = None
                await self.bus.publish(
                    EventType.NOTICE, {"kind": "db", "text": f"Scratch schema not available: {error}"}
                )
        assert self.agent is not None and self.agent.context.shell is not None
        self.agent.context.shell.extra_env = db.command_environment()
        self.context_manager.pinned.set("database", db.status_line())
        reachable = any(r.level != AccessLevel.NONE for r in db.reports.values())
        await self.bus.publish(
            EventType.NOTICE,
            {"kind": "db_status", "text": db.status_line(), "reachable": reachable},
        )

    async def _summarise(self, text: str, instruction: str) -> str:
        """For tools that condense long content (web pages): the summariser role's model."""
        request = ChatRequest(messages=[Message.system(instruction), Message.user(text)])
        response = await self.router.chat("summariser", request)
        return response.text

    def refresh_memory_pin(self) -> None:
        scope = scope_of(self.workspace) if self.workspace is not None else None
        self.context_manager.pinned.set("memory_index", combined_index(forge_home(), scope))

    async def _prepare_database_quietly(self) -> None:
        """Session start in direct mode: not a turn (no status/cost events), and never fatal."""
        if self.db is None:
            return
        try:
            await self.prepare_database()
        except (psycopg.Error, OSError, ValueError) as error:
            await self.bus.publish(
                EventType.NOTICE, {"kind": "db", "text": f"Database check failed: {error}"}
            )

    def refresh_database_pin(self) -> None:
        if self.db is not None:
            self.context_manager.pinned.set("database", self.db.status_line())

    async def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        await self.bus.publish(EventType(event_type), payload)

    def _build_context_manager(self, workspace: Workspace | None) -> ContextManager:
        def files_modified() -> list[str]:
            if workspace is None:
                return []
            return sorted({change.path for change in workspace.changes()})

        return ContextManager(
            self.router,
            self.router.config,
            compactions_dir=workspace.forge_dir / "compactions" if workspace else None,
            on_event=self._publish,
            files_modified=files_modified,
        )

    def _build_agent(self, workspace: Workspace, mode: PermissionMode) -> AgentLoop:
        # Tools beyond the defaults that every phase gets: Mode B's, OCR's, and MCP servers' once connected.
        self.extra_tools: list[Tool] = [
            *(modeb_tools() if workspace.mode_b else []),
            *(ocr_tools() if tesseract_ready(forge_home()) else []),  # D-203
        ]
        self.mcp_hub: McpHub | None = None
        settings = self.router.config.context
        context = ToolContext(
            workspace=workspace,
            shell=ShellSession(workspace, sandbox=self.router.config.shell.sandbox),
            background=BackgroundManager(),
            publish=self._publish,
            tool_cap_tokens=settings.tool_output_cap,
            shell_cap_tokens=settings.shell_output_cap,
        )
        context.db = self._build_db(workspace)
        self.refresh_profile_pin()
        web = self.router.config.web
        context.secrets = self.secrets
        context.web_search_provider = web.search_provider
        context.web_search_order = tuple(
            name
            for name in web.search_order
            if not (name == "tavily" and tavily_declined(forge_home()))  # the user said it is not available
        )
        context.web_tavily_topic = web.tavily_topic
        context.web_policy = WebPolicy.from_config(web)
        context.web_render = web.render == "auto"
        context.web_archive = web.archive_fallback
        context.hosted_search = azure_hosted_search(self.router, web.azure_search_role)
        context.summarise = self._summarise
        context.router = self.router
        context.ask_user = self._ask_user
        if workspace.mode_b:
            context.profile = self.host_profile()
            context.sensitive_terms = host_identifying_terms(context.profile)
        self.refresh_memory_pin()
        self.style: str | None = None
        gate = PermissionGate(mode, workspace.forge_dir / "permissions.json", permission_rules())
        gate.ask_new_domains = web.ask_new_domains
        loop = AgentLoop(
            self.router,
            self.bus,
            ToolRegistry(
                [
                    SpawnSubagent(),
                    AskUser(),
                    *default_tools(),
                    *(db_tools() if context.db else []),
                    *self.extra_tools,
                ]
            ),
            context,
            gate,
            self.approvals,
            self.router.config.limits.max_iterations_per_task,
            self.context_manager,
        )
        loop.on_thinking = self.stream_thinking
        context.pin = self.context_manager.pinned.set
        self._restore_todos(context)
        self.context_manager.run_hook = lambda command: self._run_hook(loop, command)
        return loop

    @property
    def busy(self) -> bool:
        return self._current_turn is not None and not self._current_turn.done()

    @property
    def inputs_empty(self) -> bool:
        return self._inputs.empty()

    async def submit(self, user_input: UserInput) -> None:
        """The single entry point for every UI. Interrupts and approval answers act immediately;
        everything else queues behind the current turn."""
        if isinstance(user_input, Interrupt):
            await self.interrupt()
            return
        if isinstance(user_input, Answer):
            if not self.questions.resolve(user_input):
                await self.bus.publish(
                    EventType.NOTICE, {"kind": "stale_answer", "text": "No such pending question."}
                )
            return
        if isinstance(user_input, Approve | Reject):
            if not self.approvals.resolve(user_input):
                await self.bus.publish(
                    EventType.NOTICE, {"kind": "stale_answer", "text": "No such pending request."}
                )
            return
        if isinstance(user_input, SendMessage):
            await self.bus.publish(EventType.USER_MESSAGE, {"text": user_input.text})
            if not user_input.text.lstrip().startswith("/"):  # slash commands don't answer cards
                await self._supersede_open_requests(user_input.text)
        if self.busy:
            await self.bus.publish(
                EventType.NOTICE, {"kind": "queued", "text": "Queued until the current turn ends"}
            )
        await self._inputs.put(user_input)

    async def _supersede_open_requests(self, text: str) -> None:
        """A message typed while approval cards or questions are open answers them (D-153); otherwise it
        would queue behind a turn that is waiting for those very cards and Forge would look deaf."""
        declined = self.approvals.reject_all(text) + self.questions.answer_all_with_text(text)
        if declined:
            await self.bus.publish(
                EventType.NOTICE,
                {
                    "kind": "request_superseded",
                    "text": f"Treated your message as the answer to {declined} open request(s); carrying on.",
                },
            )

    async def interrupt(self) -> None:
        if self.busy and self._current_turn is not None:
            self._current_turn.cancel()

    async def start_mcp(self) -> None:
        """Optional MCP servers (config mcp.enabled); their tools join every phase (spec §13B)."""
        settings = self.router.config.mcp
        if not settings.enabled or not settings.servers or self.agent is None or self.mcp_hub is not None:
            return
        self.mcp_hub = McpHub(settings.servers, self.secrets)
        tools = await self.mcp_hub.start()
        self.extra_tools += tools
        for tool in tools:
            self.agent.tools.add(tool)
        await self.bus.publish(EventType.NOTICE, {"kind": "mcp", "text": self.mcp_hub.describe()})

    async def run(self) -> None:
        await self._publish_status("idle")
        if self.workspace is not None:  # local history baseline (spec §13B); runs beside the input loop
            self._history_baseline = asyncio.create_task(asyncio.to_thread(History(self.workspace).ensure))
        await self.start_mcp()
        if self.workspace is not None and self.orchestrator is None and not self.workspace.mode_b:
            await self._prepare_database_quietly()
        if self.orchestrator is not None and self.orchestrator.needs_resume:
            await self._run_turn(self.orchestrator.resume)
        while not self.closed:
            user_input = await self._inputs.get()
            if isinstance(user_input, SendMessage):
                text = await self._prepare_message(user_input.text)
                if text is not None:
                    await self._run_turn(self._message_turn(text))
                    if self.agent is not None:
                        self.agent.turn_effort = None
            elif isinstance(user_input, SlashCommand) and user_input.text.startswith("/restructure"):
                await self._restructure(user_input.text)
            elif isinstance(user_input, SlashCommand):
                await self._commands.handle(user_input.text)
            else:
                await self.bus.publish(
                    EventType.NOTICE, {"kind": "unsupported", "text": f"'{user_input.kind}' is not used yet"}
                )

    def _message_turn(self, text: str) -> Callable[[], Awaitable[None]]:
        async def turn() -> None:
            if self.orchestrator is not None:
                await self.orchestrator.handle_message(text)  # it decides where the message goes
                return
            history_length = len(self.history)
            self.history.append(Message.user(text))
            try:
                if self.agent is not None:
                    await self.agent.run(self.history, self.stream_delta)
                else:
                    await self._plain_chat(self.stream_delta)
            except (LLMError, BudgetExceededError, ConfigError):
                if len(self.history) == history_length + 1:
                    self.history.pop()  # nothing happened yet: the user can simply resend
                raise

        return turn

    async def _restructure(self, command: str) -> None:
        instruction = command.removeprefix("/restructure").strip()
        if self.orchestrator is None or not instruction:
            await self.bus.publish(
                EventType.NOTICE,
                {
                    "kind": "command_output",
                    "text": (
                        "Usage: /restructure <how to reshape the code> (in an orchestrated workspace session)"
                    ),
                },
            )
            return
        orchestrator = self.orchestrator

        async def turn() -> None:
            await orchestrator.restructure(instruction)

        await self._run_turn(turn)

    async def _run_hook(self, loop: AgentLoop, command: str) -> tuple[bool, str]:
        """A configured hook command, run like any command: in the workspace, sandboxed (D-176)."""
        outcome = await execute(loop.context, command, 120, ".")
        return outcome.ok, outcome.content

    def _restore_todos(self, context: ToolContext) -> None:
        """A reopened project gets its todo list back from the last `todo_updated` event (D-177)."""
        for event in reversed(self.bus.events_since(0)):
            if event.type == EventType.TODO_UPDATED:
                items = [TodoItem.model_validate(i) for i in event.payload.get("items", [])]
                context.todos = [item.model_dump() for item in items]
                self.context_manager.pinned.set(TODO_PIN_SLOT, render_todos(items) if items else None)
                return

    async def stream_thinking(self, text: str) -> None:
        """A short summary of what the model is working out, shown while it waits on a slow reasoning call."""
        if text.strip():
            await self.bus.publish(EventType.THINKING_DELTA, {"text": text})

    async def stream_delta(self, delta: str) -> None:
        self._streamed.append(delta)
        await self.bus.publish(EventType.MESSAGE_DELTA, {"text": delta})

    # --- instructions, skills, message preparation (spec §13B) ---

    def repo_level_dir(self) -> Path | None:
        if self.workspace is None:
            return None
        profile = self.host_profile()
        return repo_level_dir(forge_home(), self.workspace, profile.root if profile is not None else None)

    def instruction_files(self) -> list[InstructionFile]:
        return instruction_files(
            forge_home(), self.repo_level_dir(), self.workspace.root if self.workspace else None
        )

    def refresh_instructions(self) -> None:
        self.context_manager.pinned.set(
            "instructions", render_instructions(self.instruction_files(), getattr(self, "style", None))
        )
        roots = [forge_home() / "skills"]
        level = self.repo_level_dir()
        if level is not None:
            roots.append(level / "skills")
        self.context_manager.pinned.set("skills", skills_index(discover(*roots)))

    async def _prepare_message(self, text: str) -> str | None:
        """'# note' saves an instruction (after asking where); 'think hard:' raises the effort for this turn;
        @-mentions and long pastes are expanded. Returns None when nothing is left to send."""
        stripped = text.strip()
        if stripped.startswith("#") and not stripped.startswith("##") and self.workspace is not None:
            await self._save_instruction(stripped.lstrip("#").strip())
            return None
        if stripped.lower().startswith("think hard:") and self.agent is not None:
            self.agent.turn_effort = "high"
            text = stripped[len("think hard:") :].strip()
        if self.workspace is None:
            return text
        expanded = expand_mentions(text, self.workspace, self._mention_lookup())
        for line in expanded.grants:
            await self.bus.publish(EventType.NOTICE, {"kind": "read_grant", "text": line})
        if expanded.notes:
            await self.bus.publish(
                EventType.NOTICE, {"kind": "mentions", "text": "Attached: " + ", ".join(expanded.notes)}
            )
        return expanded.text

    async def _ask_user(
        self, question: str, context: str, options: list[Any], recommended: str | None
    ) -> str:
        """The ask_user tool in a chat session: a question card with the options and a box for the user's own
        answer. A typed message also answers it (QuestionBroker.answer_all_with_text)."""
        answer = await self.questions.ask(
            EventType.QUESTION_ASKED,
            {
                "question": question,
                "context": context,
                "recommended": recommended,
                "options": [option.model_dump() for option in options],
            },
        )
        if answer.choice:
            extra = f". They added: {answer.text}" if answer.text else ""
            return f"The user chose: {answer.choice}{extra}"
        return f"The user answered: {answer.text or '(no answer)'}"

    def _mention_lookup(self) -> dict[str, object]:
        def dbr(ident: str) -> str | None:
            request = self.db.requests.get(ident) if self.db is not None else None
            return f"{request.title}\n{request.sql}\nstatus: {request.status}" if request else None

        return {"DBR": dbr}

    async def _save_instruction(self, line: str) -> None:
        files = {f.level: f for f in self.instruction_files()}
        answer = await self.questions.ask(
            EventType.QUESTION_ASKED,
            {
                "question": f"Save this instruction for Forge? “{line}”",
                "context": "Forge reads FORGE.md files at the start of every session.",
                "options": [
                    {"label": "workspace", "description": "only this requirement"},
                    {"label": "repo", "description": "every requirement on this repository / host"},
                    {"label": "user", "description": "everywhere"},
                    {"label": "cancel", "description": "don't save it"},
                ],
                "recommended": "repo",
            },
        )
        choice = (answer.choice or "").lower()
        if choice not in files:
            await self.bus.publish(EventType.NOTICE, {"kind": "command_output", "text": "Not saved."})
            return
        append_instruction(files[choice], line)
        self.refresh_instructions()
        await self.bus.publish(
            EventType.NOTICE,
            {
                "kind": "command_output",
                "text": f"Saved to the {choice}-level FORGE.md ({files[choice].path}).",
            },
        )

    async def run_message(self, text: str) -> None:
        """A custom slash command's text, handled exactly like a typed message (shown, then a turn)."""
        await self.bus.publish(EventType.USER_MESSAGE, {"text": text})
        await self._run_turn(self._message_turn(text))

    async def continue_work(self) -> None:
        """Resumes the orchestrated workflow after something outside a turn unblocked it (e.g. /db done)."""
        if self.orchestrator is not None:
            await self._run_turn(self.orchestrator.advance)

    async def _run_turn(self, work: Callable[[], Awaitable[None]]) -> None:
        self._streamed = []
        self._current_turn = asyncio.create_task(self._guarded(work))
        try:
            await self._current_turn
        except asyncio.CancelledError:
            # Keep what the user already saw, so the conversation stays coherent after an interrupt.
            if self._streamed and self.history[-1].role != "assistant":
                self.history.append(
                    Message(role="assistant", content="".join(self._streamed) + " [interrupted]")
                )
            await self.bus.publish(EventType.NOTICE, {"kind": "interrupted", "text": "Interrupted"})
            # An Interrupt cancels only the turn; if the session itself is being cancelled (shutdown),
            # swallowing it would keep run() looping forever and hang the event loop's shutdown.
            session = asyncio.current_task()
            if session is not None and session.cancelling():
                raise
        finally:
            self._current_turn = None
            await self._publish_status("idle")

    async def _guarded(self, work: Callable[[], Awaitable[None]]) -> None:
        """One turn's work with the shared error handling: errors are reported, the session lives on."""
        await self._publish_status("working")
        try:
            await work()
        except (LLMError, BudgetExceededError, ConfigError) as error:
            await self.bus.publish(EventType.ERROR, {"kind": type(error).__name__, "message": str(error)})
            return
        except Exception as error:
            log_path = self._log_internal_error()
            await self.bus.publish(
                EventType.ERROR,
                {
                    "kind": "InternalError",
                    "message": f"Forge hit an internal error ({type(error).__name__}: {error}). "
                    f"The session is still running. Details: {log_path}",
                },
            )
            return
        await self.publish_cost()

    def _log_internal_error(self) -> str:
        """Writes the traceback next to the transcript (or Forge home) and returns where."""
        folder = self.workspace.forge_dir / "logs" if self.workspace else forge_home() / "logs"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"error-{datetime.now():%Y%m%d-%H%M%S}.log"
        path.write_text(default_redactor.redact(traceback.format_exc()), encoding="utf-8")
        return str(path)

    async def _plain_chat(self, on_text_delta: Any) -> None:
        messages = await self.context_manager.prepare(self.history, [])
        response = await self.router.chat("coder", ChatRequest(messages=messages), on_text_delta)
        self.context_manager.record_usage(response.usage)
        model_key = self.router.model_for_role("coder")
        self.history.append(response.to_message(model_key))
        await self.bus.publish(
            EventType.MESSAGE_DONE,
            {
                "text": response.text,
                "model": model_key,
                "served_model": response.served_model,
                "finish_reason": response.finish_reason,
                "usage": response.usage.model_dump(),
                "cost_usd": round(self.router.cost.cost_of(model_key, response.usage), 6),
            },
        )

    def _usage_where(self) -> tuple[str, str | None]:
        """The activity and task a model call is filed under (spec §7, D-128/D-131: no fixed phase — a
        loose label for the usage ledger, not control flow)."""
        if self.orchestrator is None:
            return "direct", None
        state = self.orchestrator.state
        if state.current_task:
            return "execute", state.current_task
        return "working" if state.started and not state.exported else "requirement", None

    async def publish_cost(self) -> None:
        await self.bus.publish(EventType.COST_UPDATED, self.router.cost.summary())

    async def _publish_status(self, state: str) -> None:
        payload: dict[str, Any] = {"state": state, "roles": dict(self.router.role_models)}
        if self.agent is not None:
            payload["permission_mode"] = self.agent.gate.mode
        await self.bus.publish(EventType.STATUS_CHANGED, payload)

    def reset_history(self) -> None:
        self.history = [Message.system(self.system_prompt)]
        self.context_manager.clear(self.history)

    async def close(self) -> None:
        self.closed = True
        await self.interrupt()
        if self._current_turn is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await self._current_turn
        if self.orchestrator is not None:
            await self.orchestrator.wait_idle()
        if self.agent is not None and self.agent.context.background is not None:
            await self.agent.context.background.stop_all()
        hub = getattr(self, "mcp_hub", None)
        if hub is not None:
            await hub.close()
        if self.agent is not None and self.agent.context.browser is not None:
            with contextlib.suppress(Exception):
                await self.agent.context.browser.close()
