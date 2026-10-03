"""Terminal client (spec §4). A thin consumer of engine events; all logic lives in the engine."""

from __future__ import annotations

import asyncio
import contextlib
import sys
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console
from rich.markdown import Markdown
from rich.rule import Rule
from rich.text import Text

from forge.engine.session_host import SessionHost
from forge.llm.cost import format_money
from forge.protocol.events import Event, EventType
from forge.protocol.inputs import Answer, Approve, Interrupt, Reject, SendMessage, SlashCommand, UserInput

WELCOME = "Forge — type a message, /help for commands, Esc to interrupt, Ctrl+D to quit."
DIFF_PREVIEW_LINES = 40


class ConsoleState:
    """Which approval, question or user action (if any) the next typed line answers."""

    def __init__(self) -> None:
        self.pending_approval: str | None = None
        self.pending_question: str | None = None
        self.question_options: list[str] = []
        self.pending_action: str | None = None
        # The status bar (spec M10): kept current from events.
        self.current_task: str | None = None
        self.cadence: str = ""
        self.context_percent: float | None = None
        self.busy = False
        self.permission_mode: str = ""


def track_status(event: Event, state: ConsoleState) -> None:
    payload = event.payload
    if event.type == EventType.STATUS_CHANGED:
        state.busy = payload.get("state") == "working"
        state.permission_mode = str(payload.get("permission_mode") or state.permission_mode)
    elif event.type == EventType.CONTEXT_UPDATED:
        state.context_percent = payload.get("percent")
    elif event.type == EventType.TASK_LIST_UPDATED:
        state.current_task = payload.get("current_task")
        state.cadence = str(payload.get("cadence") or "")


def status_bar(host: SessionHost, state: ConsoleState) -> str:
    """One line under the prompt: task, working/idle, context use, cost, permission mode."""
    parts = []
    if state.current_task:
        parts.append(f"task {state.current_task}")
    if state.cadence and state.cadence != "default":
        parts.append(f"cadence {state.cadence.replace('_', ' ')}")
    parts.append("working… (Esc stops)" if state.busy else "idle")
    if state.context_percent is not None:
        parts.append(f"ctx {state.context_percent:.0f}%")
    parts.append(format_money(host.router.cost.total_usd, host.router.config.cost))
    if state.permission_mode:
        parts.append(f"mode {state.permission_mode}")
    return "  " + "  |  ".join(parts)


def render_event(event: Event, console: Console, state: ConsoleState) -> None:
    payload = event.payload
    kind = event.type
    track_status(event, state)
    if kind == EventType.MESSAGE_DELTA:
        # Streamed text is written raw (no markup parsing) so model output can't inject styles.
        sys.stdout.write(payload["text"])
        sys.stdout.flush()
    elif kind == EventType.THINKING_DELTA:
        console.print(Text(f"  … {payload['text'].strip()[:300]}", style="dim italic"))
    elif kind == EventType.MESSAGE_DONE:
        sys.stdout.write("\n")
        sys.stdout.flush()
    elif kind == EventType.TOOL_CALL_STARTED:
        console.print(Text(f"● {payload.get('summary')}", style="cyan"))
    elif kind == EventType.TOOL_CALL_FINISHED:
        mark, style = ("  ✓", "green") if payload.get("ok") else ("  ✗", "red")
        first = (payload.get("preview") or "").strip().splitlines()[:1]
        console.print(
            Text(f"{mark} {payload.get('duration_s')}s {first[0][:150] if first else ''}", style=style)
        )
    elif kind == EventType.FILE_CHANGED:
        render_diff(payload, console)
    elif kind == EventType.APPROVAL_REQUESTED and payload.get("markdown"):
        state.pending_approval = str(payload["id"])
        console.print(Rule(str(payload.get("summary")), style="yellow"))
        console.print(Markdown(str(payload["markdown"])))
        console.print(Text("  [y] approve   [n <what to change>] request changes", style="bold yellow"))
    elif kind == EventType.QUESTION_ASKED:
        render_question(payload, console, state)
    elif kind == EventType.USER_ACTION_REQUESTED:
        state.pending_action = str(payload["id"])
        console.print(Rule(f"Please do this: {payload.get('title')}", style="magenta"))
        for number, step in enumerate(payload.get("steps") or [], start=1):
            console.print(Text(f"  {number}. {step}"))
        if payload.get("verify_command"):
            console.print(Text(f"  Forge will check with: {payload['verify_command']}", style="dim"))
        console.print(Text("  [done]   [skip]   [cant <why>]", style="bold magenta"))
    elif kind == EventType.APPROVAL_REQUESTED:
        state.pending_approval = str(payload["id"])
        console.print(Text(f"\nApproval needed: {payload.get('summary')}", style="bold yellow"))
        console.print(Text(f"  why: {payload.get('reason')}", style="yellow"))
        prefix = payload.get("can_remember_prefix")
        choices = (
            "[y] allow once"
            + (f"  [a] always allow '{prefix}'" if prefix else "")
            + "  [n <instead...>] deny"
        )
        console.print(Text(f"  {choices}", style="yellow"))
    elif kind == EventType.NOTICE:
        console.print(Text(payload.get("text") or _describe_notice(payload), style="dim"))
    elif kind == EventType.ERROR:
        console.print(Text(f"Error ({payload.get('kind')}): {payload.get('message')}", style="red"))
    elif kind == EventType.COST_UPDATED:
        console.print(
            Text(f"[{payload.get('calls')} calls · ${payload.get('total_usd', 0):.4f}]", style="dim")
        )


def render_question(payload: dict[str, Any], console: Console, state: ConsoleState) -> None:
    state.pending_question = str(payload["id"])
    options = payload.get("options") or []
    state.question_options = [str(option.get("label")) for option in options]
    console.print(Rule(str(payload.get("question")), style="cyan"))
    if payload.get("context"):
        console.print(Text(str(payload["context"]), style="dim"))
    for number, option in enumerate(options, start=1):
        star = "  (recommended)" if option.get("label") == payload.get("recommended") else ""
        console.print(Text(f"  {number}. {option.get('label')}{star}", style="bold"))
        for field in ("description", "pros", "cons", "risks"):
            if option.get(field):
                console.print(Text(f"       {field}: {option[field]}", style="dim"))
    console.print(Text("  Answer with a number, or type your own answer.", style="bold cyan"))


def reply_for(line: str, state: ConsoleState) -> UserInput | None:
    """Turns a typed line into the answer for whatever is waiting; None if nothing is."""
    text = line.strip()
    if state.pending_question:
        question, state.pending_question = state.pending_question, None
        if text.isdigit() and 1 <= int(text) <= len(state.question_options):
            return Answer(question_id=question, choice=state.question_options[int(text) - 1])
        return Answer(question_id=question, text=text)
    if state.pending_action:
        word, _, rest = text.partition(" ")
        if word.lower() not in ("done", "skip", "cant", "can't"):
            return None
        action, state.pending_action = state.pending_action, None
        return Answer(
            question_id=action, choice=word.lower().replace("can't", "cant"), text=rest.strip() or None
        )
    if state.pending_approval:
        answer = answer_for(text, state.pending_approval)
        if answer is not None:
            state.pending_approval = None
        return answer
    return None


def render_diff(payload: dict[str, object], console: Console) -> None:
    op = payload.get("op")
    console.print(Text(f"  {op}: {payload.get('path')}", style="bold"))
    lines = str(payload.get("diff") or "").splitlines()
    for line in lines[2 : DIFF_PREVIEW_LINES + 2]:  # skip the ---/+++ header
        style = (
            "green"
            if line.startswith("+")
            else "red"
            if line.startswith("-")
            else "cyan"
            if line.startswith("@@")
            else "dim"
        )
        console.print(Text(f"    {line}", style=style))
    if len(lines) > DIFF_PREVIEW_LINES + 2:
        console.print(Text(f"    … {len(lines) - DIFF_PREVIEW_LINES - 2} more diff lines", style="dim"))


def _describe_notice(payload: dict[str, object]) -> str:
    kind = payload.get("kind")
    if kind == "retry":
        return (
            f"Retrying {payload.get('model')} in {payload.get('delay_s')}s (attempt {payload.get('attempt')})"
        )
    if kind == "fallback":
        return f"Switched {payload.get('role')} from {payload.get('from_model')} to {payload.get('to_model')}"
    return str(payload)


def answer_for(line: str, request_id: str) -> UserInput | None:
    """Turns a typed reply into an approval answer; None if the line isn't one."""
    word, _, rest = line.strip().partition(" ")
    word = word.lower()
    if word in ("y", "yes"):
        return Approve(request_id=request_id)
    if word in ("a", "always"):
        return Approve(request_id=request_id, scope="prefix")
    if word in ("n", "no"):
        return Reject(request_id=request_id, instruction=rest.strip() or None)
    return None


async def _render_loop(host: SessionHost, console: Console, state: ConsoleState) -> None:
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    try:
        async for event in subscription:
            render_event(event, console, state)
    finally:
        subscription.close()


def _key_bindings(host: SessionHost) -> KeyBindings:
    bindings = KeyBindings()

    @bindings.add("escape", eager=True)
    def _interrupt(event: KeyPressEvent) -> None:
        asyncio.get_running_loop().create_task(host.submit(Interrupt()))

    return bindings


async def run_console(host: SessionHost) -> None:
    console = Console()
    state = ConsoleState()
    console.print(WELCOME, style="bold", markup=False)
    if host.workspace is not None:
        console.print(f"Workspace: {host.workspace.root}", markup=False)
    engine = asyncio.create_task(host.run())
    renderer = asyncio.create_task(_render_loop(host, console, state))
    prompt: PromptSession[str] = PromptSession(
        key_bindings=_key_bindings(host),
        bottom_toolbar=lambda: status_bar(host, state),
        refresh_interval=1.0,
    )
    try:
        with patch_stdout(raw=True):
            while not host.closed:
                try:
                    text = await prompt.prompt_async("> ")
                except (EOFError, KeyboardInterrupt):
                    break
                text = text.strip()
                if not text:
                    continue
                waiting = (
                    state.pending_question
                    or state.pending_action
                    or (state.pending_approval and state.pending_approval in host.approvals.pending_ids)
                )
                if waiting and not text.startswith("/"):
                    answer = reply_for(text, state)
                    if answer is None:
                        console.print("Please answer the request above first.", markup=False)
                        continue
                    await host.submit(answer)
                elif text.startswith("/"):
                    await host.submit(SlashCommand(text=text))
                else:
                    await host.submit(SendMessage(text=text))
                await asyncio.sleep(0.05)  # let /exit take effect before prompting again
    finally:
        await host.close()
        for task in (engine, renderer):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        config = host.router.config.cost
        console.print(f"Session cost: {format_money(host.router.cost.total_usd, config)}", markup=False)
