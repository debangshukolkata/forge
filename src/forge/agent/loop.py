"""The core agent loop (spec §8): model call -> tool calls -> results -> repeat until no tool calls."""

from __future__ import annotations

import asyncio
import contextlib
import time
import traceback
from dataclasses import dataclass
from datetime import date
from importlib import resources
from typing import Any

from pydantic import ValidationError

from forge.agent.escalation import Escalator
from forge.agent.stuck import StuckDetector, content_hash
from forge.config import forge_home
from forge.context.manager import ContextManager
from forge.engine.approvals import ApprovalBroker
from forge.engine.events import EventBus, EventType
from forge.errors import ForgeError, LLMContentFilterError, LLMContextLengthError
from forge.learning.improve import prompt_override
from forge.llm.base import ChatRequest, LLMResponse, Message, TextDeltaCallback, ToolCall
from forge.llm.router import LLMRouter
from forge.llm.tool_args import parse_error_result
from forge.safety.injection import flag
from forge.safety.permissions import Decision, PermissionGate
from forge.tools.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.powershell import ps_quote
from forge.tools.registry import ToolRegistry
from forge.tools.shell import execute, is_test_command
from forge.verify.parsers import error_signature, signature
from forge.workspace.workspace import Workspace

PREVIEW_CHARS = 1500
CONTENT_FILTER_NOTE = (
    "Your previous reply was blocked by the Azure content filter. Rephrase it neutrally and "
    "professionally, and continue the task."
)
INTERRUPTED = "Interrupted by the user before this tool call finished."
MAX_CONTINUATIONS = 2
EMPTY_TURN_NOTE = (
    "You ended your turn without a reply or a tool call. Continue the task with tool calls, or give "
    "your final answer if the task is done."
)
CUT_OFF_NOTE = (
    "Your previous reply was cut off at the output limit. Continue exactly where you stopped: keep it "
    "short, and use tool calls if work remains."
)
FAILURE_HEAD_CHARS = 400
FAILURE_TAIL_CHARS = 1500


def _preview(content: str, ok: bool) -> str:
    """The start of a result for the UI. A failure keeps its end too: test runners and tracebacks put the
    actual error last, and the Run map's failures drawer (D-122) shows it."""
    if ok or len(content) <= FAILURE_HEAD_CHARS + FAILURE_TAIL_CHARS:
        return content[:PREVIEW_CHARS] if ok else content
    return content[:FAILURE_HEAD_CHARS] + "\n…\n" + content[-FAILURE_TAIL_CHARS:]


def system_prompt(workspace: Workspace) -> str:
    name = "agent/prompts/system_modeb.md" if workspace.mode_b else "agent/prompts/system.md"
    template = resources.files("forge").joinpath(name).read_text(encoding="utf-8")
    override = prompt_override(forge_home(), "system_modeb" if workspace.mode_b else "system")
    if override:  # approved tier-2 tweaks (spec §12.5), never edits to the built-in file
        template += "\n\n" + override.replace("{", "{{").replace("}", "}}")
    env = workspace.info.python_env
    return template.format(
        workspace=workspace.root,
        repo_path=workspace.info.repo_path,
        app_subfolder=workspace.info.app_subfolder,
        interpreter=env.python if env else "none found yet (ask the user)",
        date=date.today().isoformat(),
    )


HOOKED_TOOLS = {"write_file", "edit_file", "multi_edit"}
HOOK_TIMEOUT_S = 120


class AgentLoop:
    def __init__(
        self,
        router: LLMRouter,
        bus: EventBus,
        tools: ToolRegistry,
        context: ToolContext,
        gate: PermissionGate,
        approvals: ApprovalBroker,
        max_iterations: int,
        context_manager: ContextManager,
    ) -> None:
        self.router = router
        self.bus = bus
        self.tools = tools
        self.context = context
        self.gate = gate
        self.approvals = approvals
        self.max_iterations = max_iterations
        self.context_manager = context_manager
        self.role = "coder"  # subagents run on other roles' models (reviewer, debugger)
        self.effort: str | None = None  # /effort: overrides the model's configured reasoning effort
        self.turn_effort: str | None = None  # "think hard:" raises it for one turn
        self.escalate = True  # subagents report back instead of escalating
        self.stuck = StuckDetector(max_fix_attempts=router.config.limits.max_fix_attempts)
        self.escalator = Escalator(self)
        self._observations: list[_Observation] = []

    async def run(self, history: list[Message], on_text_delta: TextDeltaCallback) -> None:
        """Works until the model stops calling tools. Mutates history; keeps call/result pairs valid."""
        continuations = 0
        for _ in range(self.max_iterations):
            # After a cut-off reply, think less so the answer fits in the output limit (D-060).
            response = await self._chat(
                history, on_text_delta, "low" if continuations else (self.turn_effort or self.effort)
            )
            model_key = self.router.model_for_role(self.role)
            history.append(response.to_message(model_key))
            if response.text or not response.tool_calls:
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
            if not response.tool_calls:
                cut_off = response.finish_reason == "length"
                empty = not response.text.strip()
                if (cut_off or empty) and continuations < MAX_CONTINUATIONS:
                    continuations += 1
                    history.append(Message.system(CUT_OFF_NOTE if cut_off else EMPTY_TURN_NOTE))
                    await self.bus.publish(
                        EventType.NOTICE,
                        {
                            "kind": "continuing",
                            "text": "The reply hit the output limit; asking the model to continue.",
                        },
                    )
                    continue
                return
            continuations = 0
            results: dict[str, Message] = {}
            try:
                await self._run_calls(response.tool_calls, results)
            finally:  # also on interrupt: every call gets a result, in the original order
                history.extend(
                    results.get(call.id) or Message.tool_result(call.id, INTERRUPTED)
                    for call in response.tool_calls
                )
            if self.context.end_turn:  # a phase tool finished its phase (orchestrator, M6)
                return
            if await self._check_stuck(history):
                return
        await self.bus.publish(
            EventType.NOTICE,
            {
                "kind": "iteration_limit",
                "text": f"Stopped after {self.max_iterations} steps (limits.max_iterations_per_task). "
                "Say 'continue' to go on.",
            },
        )

    async def _chat(
        self, history: list[Message], on_text_delta: TextDeltaCallback, reasoning_effort: str | None = None
    ) -> LLMResponse:
        tools = self.tools.specs(read_only_only=self.gate.mode == "plan")
        request = ChatRequest(
            messages=await self.context_manager.prepare(history, tools),
            tools=tools,
            reasoning_effort=reasoning_effort,
        )
        try:
            response = await self.router.chat(self.role, request, on_text_delta)
        except LLMContextLengthError:
            # The estimate was too optimistic: trim hard and try once more (spec §10.4 tier 3).
            await self.context_manager.emergency(history)
            request = ChatRequest(
                messages=await self.context_manager.prepare(history, tools),
                tools=tools,
                reasoning_effort=reasoning_effort,
            )
            response = await self.router.chat(self.role, request, on_text_delta)
        except LLMContentFilterError:
            response = await self._rephrase(request, on_text_delta)
        self.context_manager.record_usage(response.usage)
        parts = self.context_manager.breakdown(history, tools)
        await self.bus.publish(
            EventType.CONTEXT_UPDATED,
            {
                "percent": parts.percent,
                "usable": parts.usable,
                "fixed": parts.fixed,
                "pinned": parts.pinned,
                "history": parts.history,
                "free": parts.free,
                "compactions": self.context_manager.compactions,
            },
        )
        return response

    async def _rephrase(self, request: ChatRequest, on_text_delta: TextDeltaCallback) -> LLMResponse:
        """Only the model can rephrase its own reply (DECISIONS D-030); one retry, then surface it."""
        await self.bus.publish(
            EventType.NOTICE,
            {
                "kind": "content_filter",
                "text": "Blocked by the content filter; asking the model to rephrase.",
            },
        )
        retry = request.model_copy(
            update={"messages": [*request.messages, Message.system(CONTENT_FILTER_NOTE)]}
        )
        return await self.router.chat("coder", retry, on_text_delta)

    async def _run_calls(self, calls: list[ToolCall], results: dict[str, Message]) -> None:
        """Consecutive read-only calls run in parallel; anything that changes state runs alone, in order."""
        batch: list[ToolCall] = []
        for call in calls:
            tool = self.tools.get(call.name)
            if tool is not None and tool.read_only and call.parse_error is None:
                batch.append(call)
                continue
            await self._run_batch(batch, results)
            batch = []
            results[call.id] = await self._run_one(call)
        await self._run_batch(batch, results)

    async def _run_batch(self, batch: list[ToolCall], results: dict[str, Message]) -> None:
        if batch:
            for call, message in zip(
                batch, await asyncio.gather(*(self._run_one(c) for c in batch)), strict=True
            ):
                results[call.id] = message

    async def _run_one(self, call: ToolCall) -> Message:
        tool = self.tools.get(call.name)
        if tool is None:
            return Message.tool_result(
                call.id, f"Error: unknown tool '{call.name}'. Available: {', '.join(self.tools.names())}"
            )
        if call.parse_error is not None:
            return parse_error_result(call)
        try:
            args = tool.Args.model_validate(call.arguments or {})
        except ValidationError as error:
            return Message.tool_result(call.id, f"Error: invalid arguments for {call.name}: {error}")
        summary = tool.summary(args)
        self.context.step += 1
        command = tool.command(args, self.context)
        scope = self.context.shell.scope() if command and self.context.shell else None
        decision = self.gate.decide(
            tool.name, tool.read_only, command, scope, own_files_only=tool.own_files_only(args, self.context)
        )
        await self.bus.publish(
            EventType.TOOL_CALL_STARTED, {"id": call.id, "name": call.name, "summary": summary}
        )
        started = time.perf_counter()
        if decision.verdict == "deny":
            result = ToolResult(ok=False, content=f"Not allowed: {decision.reason}")
        else:
            result = (
                await self._approved_run(tool, args, summary, command, decision)
                if decision.verdict == "ask"
                else await self._execute(tool, args)
            )
            if result.ok and tool.name in HOOKED_TOOLS and self.router.config.hooks.post_edit:
                result = await self._post_edit_hooks(args, result)
        await self.bus.publish(
            EventType.TOOL_CALL_FINISHED,
            {
                "id": call.id,
                "name": call.name,
                "ok": result.ok,
                "summary": summary,
                "preview": _preview(result.content, result.ok),
                "duration_s": round(time.perf_counter() - started, 2),
            },
        )
        self._observations.append(_Observation(tool.name, call.arguments or {}, args, command, result))
        # Every result is capped here (spec §10.3), whatever the tool did itself.
        content, _ = self.context.cap_output(result.content, tool.output_kind)
        content, marker = flag(content)
        if marker:
            await self.bus.publish(
                EventType.NOTICE,
                {
                    "kind": "injection",
                    "text": f"Possible prompt injection in {call.name} output ({summary}): '{marker}'.",
                },
            )
        return Message.tool_result(call.id, content if result.ok else f"Error: {content}")

    async def _post_edit_hooks(self, args: ToolArgs, result: ToolResult) -> ToolResult:
        """config hooks.post_edit (e.g. "ruff format {file}") after each successful edit; the output is
        appended to the edit's result so the model sees formatter/linter feedback right away."""
        path = getattr(args, "path", None)
        if not isinstance(path, str) or self.context.shell is None:
            return result
        notes = []
        for template in self.router.config.hooks.post_edit:
            command = template.replace("{file}", ps_quote(path))
            outcome = await execute(self.context, command, HOOK_TIMEOUT_S, ".")
            verdict = "ok" if outcome.ok else "FAILED"
            notes.append(f"[post-edit hook: {command} -> {verdict}]\n{outcome.content[-1500:]}")
        with contextlib.suppress(OSError, ValueError, ForgeError):
            # A formatter may have rewritten the file: what's on disk now is what the model has "read".
            self.context.reads.record(path, self.context.workspace.path_of(path).read_bytes())
        return ToolResult(ok=result.ok, content=result.content + "\n" + "\n".join(notes), meta=result.meta)

    async def _check_stuck(self, history: list[Message]) -> bool:
        """Feeds this step's tool results to the stuck detector; escalates on a signal (spec §13.3).
        Returns True when the turn must stop."""
        observations, self._observations = self._observations, []
        if not self.escalate:
            return False
        seen_errors: set[str] = set()
        for observation in observations:
            facts = observation.facts(self.context)
            # Parallel calls failing the same way in one step are one failure, not three.
            if facts["error_signature"] in seen_errors:
                continue
            if facts["error_signature"]:
                seen_errors.add(facts["error_signature"])
            signal = self.stuck.observe(**facts)
            if signal is not None:
                return await self.escalator.handle(signal, history)
        return False

    async def _approved_run(
        self, tool: Tool, args: ToolArgs, summary: str, command: str | None, decision: Decision
    ) -> ToolResult:
        answer = await self.approvals.request(
            {
                "tool": tool.name,
                "summary": summary,
                "command": command,
                "reason": decision.reason,
                "can_remember_prefix": decision.command_prefix,
                "always_ask": decision.always_ask,
            }
        )
        if not answer.approved:
            note = f" The user said: {answer.instruction}" if answer.instruction else ""
            return ToolResult(ok=False, content=f"The user declined this action.{note}")
        if answer.scope == "prefix" and decision.command_prefix:
            self.gate.allow_prefix(decision.command_prefix)
        return await self._execute(tool, args)

    async def _execute(self, tool: Tool, args: ToolArgs) -> ToolResult:
        try:
            return await tool.run(args, self.context)
        except ForgeError as error:
            return ToolResult(ok=False, content=str(error))
        except (OSError, ValueError) as error:
            return ToolResult(ok=False, content=f"{type(error).__name__}: {error}")
        except Exception as error:  # a tool bug must not end the session (seen live)
            log = self.context.workspace.forge_dir / "logs" / f"tool-error-{int(time.time())}.log"
            with contextlib.suppress(OSError):
                log.parent.mkdir(parents=True, exist_ok=True)
                self.context.workspace.jail.check(log).write_text(traceback.format_exc(), encoding="utf-8")
            return ToolResult(
                ok=False,
                content=f"The {tool.name} tool failed unexpectedly ({type(error).__name__}: {error}). This "
                "is a Forge bug, not your mistake; the details are logged. Check your inputs or continue "
                "another way.",
            )


@dataclass
class _Observation:
    tool: str
    arguments: dict[str, Any]
    args: ToolArgs
    command: str | None
    result: ToolResult

    def facts(self, context: ToolContext) -> dict[str, Any]:
        """What the stuck detector needs: the error signature, the file's new content, test success."""
        ok = self.result.ok
        is_test = self.tool in ("run_tests", "verify") or bool(self.command and is_test_command(self.command))
        path = getattr(self.args, "path", None)
        file_hash = None
        if ok and isinstance(path, str):
            try:
                file_hash = content_hash(context.workspace.path_of(path).read_bytes())
            except (OSError, ValueError, ForgeError):
                file_hash = None
        return {
            "tool": self.tool,
            "arguments": self.arguments,
            "ok": ok,
            "error_signature": None
            if ok
            else (error_signature(self.result.content) or signature(self.result.content[:200])),
            "file_path": path if isinstance(path, str) else None,
            "file_content_hash": file_hash,
            "tests_passed": ok and is_test,
        }
