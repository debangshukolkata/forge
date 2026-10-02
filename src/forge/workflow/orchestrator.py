"""The requirement workflow (spec §7, D-128/D-130/D-132): a flat agent loop, not a fixed phase state
machine. Forge understands, explores, plans and executes a requirement using its own judgment about when to
ask the user or check in — the same way this assistant works — instead of marching through mandatory
CLARIFY/PLAN/REVIEW gates. Change requests and RESTRUCTURE (§6.7) reuse the same loop with a smaller brief.

State is saved after every change, so a killed run resumes automatically and silently on reopen (D-132):
no "resume or start fresh?" prompt, no phase to restore — just the task list, the requirement, and the
cadence (D-130) the user last asked for, which persists across the interruption.
"""

from __future__ import annotations

import asyncio
from importlib import resources
from typing import TYPE_CHECKING, Any

from forge.llm.base import Message
from forge.modeb.assumptions import AssumptionRegister
from forge.modeb.output import build_modeb_output
from forge.parity.history import History
from forge.protocol.events import EventType
from forge.subagents.spawn_tool import SpawnSubagent
from forge.toolkit.base import Tool, ToolContext, ToolResult
from forge.toolkit.powershell import ps_quote
from forge.toolkit.pytest_report import parse_pytest
from forge.toolkit.shell import execute
from forge.tools.interaction import (
    AskUser,
    OptionSpec,
    ProposePlan,
    ProposeRequirements,
    RequestUserAction,
    TaskSpec,
    TaskUpdate,
    UpdatePlan,
)
from forge.tools.registry import ToolRegistry, db_tools, default_tools
from forge.workflow.reports import closing_message, final_report
from forge.workflow.state import Cadence, StateStore, Task
from forge.workspace.output import build_output

if TYPE_CHECKING:
    from forge.engine.session_host import SessionHost

MAX_NUDGES = 1
# No -q: repos often set it in addopts, and -qq hides the summary line the parser reads.
PYTEST_ARGS = "-rfE --tb=short --no-header -p no:cacheprovider"
FULL_SUITE_TIMEOUT_S = 900
RESUMED_NOTE = (
    "\n\nResumed after an interruption: first check what is already done (files modified are pinned)."
)
NUDGE = (
    "Finish the current step: verify and call task_update, or ask the user if you are blocked. "
    "Don't stop without one of these."
)
FREE_HAND_PHRASES = (
    "don't ask me",
    "dont ask me",
    "go ahead with the recommended",
    "you have a free hand",
    "free hand",
    "proceed without asking",
    "don't wait for my approval",
)
ASK_EVERY_STEP_PHRASES = (
    "ask me before every step",
    "ask me every step",
    "ask before every step",
    "check with me",
    "check in with me",
    "ask me first from now on",
)


def requirement_instructions() -> dict[str, str]:
    text = resources.files("forge").joinpath("workflow/prompts/phases.md").read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    for block in text.split("\n## ")[1:]:
        name, _, body = block.partition("\n")
        sections[name.strip()] = body.strip()
    return sections


def detect_cadence(text: str) -> Cadence | None:
    """Recognises a cadence instruction in a chat message (D-130) — the same way this assistant follows a
    mid-conversation 'go ahead, don't ask me' or 'ask me before every step' until told otherwise. Returns
    None when the message doesn't look like a cadence instruction, so the caller leaves cadence unchanged."""
    lowered = text.lower()
    if any(phrase in lowered for phrase in FREE_HAND_PHRASES):
        return "free_hand"
    if any(phrase in lowered for phrase in ASK_EVERY_STEP_PHRASES):
        return "ask_every_step"
    return None


class Orchestrator:
    def __init__(self, host: SessionHost) -> None:
        assert host.workspace is not None and host.agent is not None
        self.host = host
        self.workspace = host.workspace
        self.store = StateStore(self.workspace)
        self.state = self.store.load()
        self.instructions = requirement_instructions()
        self.context: ToolContext = host.agent.context
        self.context.interaction = self
        self._publishing: set[asyncio.Task[Any]] = set()
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._task_start_step = 0
        self._restructure_baseline: tuple[bool, str] | None = None
        self._apply_cadence()
        self._refresh_pinned()

    # --- entry points ---

    @property
    def needs_resume(self) -> bool:
        return self.state.started and not self.state.exported

    async def handle_message(self, text: str) -> None:
        cadence = detect_cadence(text)
        if cadence is not None:
            self.set_cadence(cadence)
        if not self.state.started:
            self.state.requirement = text
            self.state.started = True
            self._save()
        elif self.state.exported:
            self._start_change(text, restructure=False)
        else:
            self.host.history.append(Message.user(text))
        await self.advance()

    async def resume(self) -> None:
        await self._notice("resume", f"Resuming: {self.state.resume_summary()}")
        await self.host.prepare_database()
        if self.state.current_task:
            self._start_task(self.state.task(self.state.current_task), resumed=True)  # type: ignore[arg-type]
        await self.advance()

    async def restructure(self, instruction: str) -> None:
        """§6.7: behaviour must not change, so the tests are run before and after and compared."""
        self._restructure_baseline = await self._run_tests()
        self._start_change(instruction, restructure=True)
        await self.advance()

    def db_request_resolved(self, request_id: str, done: bool, note: str) -> bool:
        """/db done|cant|skip: tasks blocked on the request go back to the board (spec §9.5.2). When it
        can't be run, the task is retried with the reason so the agent picks a workaround. Returns True
        when there is work to continue."""
        waiting = [t for t in self.state.tasks if t.status == "blocked" and request_id in t.blocked_reason]
        for task in waiting:
            task.status = "pending"
            task.blocked_reason = ""
            if not done:
                task.description += (
                    f"\n\nNote: {request_id} will not be run ({note or 'no reason given'}). "
                    "Find a workaround that doesn't need it (e.g. keep the change in DB_CHANGES.sql "
                    "and mark the check server-run), or ask the user."
                )
        if waiting and self.state.exported:  # work resumes: this is no longer a finished, resume-safe state
            self.state.exported = False
        self._save()
        return bool(waiting)

    # --- the flat loop (spec §7, D-128) ---

    async def advance(self) -> None:
        """Runs (or continues) the requirement: brief the model once, then let it work — reading,
        exploring, planning out loud only at real forks, executing tasks — using its own judgment about
        when to check in, until it ends its turn to wait for the user or every task is settled."""
        if not self.state.started:
            return
        first_brief = not self._briefed()
        kind = self._change_kind()
        if first_brief and not kind and not self.workspace.mode_b:
            await self.host.prepare_database()
        if first_brief:
            text = self._format(kind or "requirement")
            self.host.history.append(Message.system(text))
        if not await self._run_agent(self._tools()):
            return  # waiting for the user's reply
        if self.state.tasks and self.state.next_task() is None and not self._has_open_tasks():
            await self._export()

    def _has_open_tasks(self) -> bool:
        return any(t.status in ("pending", "in_progress") for t in self.state.tasks)

    async def _run_agent(self, tools: ToolRegistry) -> bool:
        agent = self.host.agent
        assert agent is not None
        agent.tools = tools
        self.context.end_turn = False
        try:
            while (task := self.state.next_task()) is not None or not self.state.tasks:
                if task is not None and (self.state.current_task != task.id or task.status != "in_progress"):
                    self._start_task(task)
                for nudge in range(MAX_NUDGES + 1):
                    await agent.run(self.host.history, self.host.stream_delta)
                    if self.context.end_turn:
                        break
                    if nudge == MAX_NUDGES:
                        return False  # waiting for the user's reply
                    self.host.history.append(Message.system(NUDGE))
                self.context.end_turn = False
                if not self.state.tasks:  # the model hasn't broken the work into tasks yet
                    return True
            return True
        finally:
            self.context.end_turn = False
            self._save()

    # --- helpers used by the loop ---

    def _tools(self) -> ToolRegistry:
        return ToolRegistry(
            [
                *default_tools(),
                SpawnSubagent(),
                *self._db_tools(),
                *self.host.extra_tools,  # Mode B profile/contract tools, MCP server tools
                AskUser(),
                ProposeRequirements(),
                ProposePlan(),
                UpdatePlan(),
                TaskUpdate(),
                RequestUserAction(),
            ]
        )

    def _db_tools(self) -> list[Tool]:
        return db_tools() if self.host.db is not None else []

    def _briefed(self) -> bool:
        marker = self.instructions[self._change_kind() or "requirement"][:40]
        return any(m.role == "system" and m.content.startswith(marker) for m in self.host.history)

    def _change_kind(self) -> str:
        if self.state.restructuring:
            return "restructure"
        return "change" if self.state.change_request else ""

    def _start_task(self, task: Task, resumed: bool = False) -> None:
        previous = [t for t in self.state.tasks if t.status == "done"]
        handoff = previous[-1].handoff_note if previous else None
        task.status = "in_progress"
        task.attempts += 1
        self.state.current_task = task.id
        brief = self._format(self._change_kind() or "requirement", task=self._task_text(task))
        if resumed:
            brief += RESUMED_NOTE
        self.host.context_manager.reset_for_task(self.host.history, brief, handoff)
        self._task_start_step = self.context.step
        self._save()

    async def _export(self) -> None:
        """Builds output/ once every task is settled (done or blocked). Judgment-based, not a mandatory
        gated REVIEW step (D-132): Forge has already verified as it went; this just packages the result."""
        output = build_modeb_output(self.workspace) if self.workspace.mode_b else build_output(self.workspace)
        report = final_report(self.state, self._requirement_text(), output, self.workspace, self.host.db)
        if self._restructure_baseline is not None:
            passed_before, _ = self._restructure_baseline
            passed_after, summary_after = await self._run_tests()
            same = passed_before == passed_after
            report += (
                f"\n\n## Restructure check\n\nTests before: {'PASSED' if passed_before else 'FAILED'}; "
                f"after: {'PASSED' if passed_after else 'FAILED'} ({'same' if same else 'DIFFERENT'}).\n"
                f"```\n{summary_after}\n```\n"
            )
            self._restructure_baseline = None
        self.store.write_document("reports/final.md", report)
        await self.host.bus.publish(
            EventType.MESSAGE_DONE, {"text": closing_message(self.state, output), "model": "forge"}
        )
        self.state.change_request, self.state.restructuring = "", False
        self.state.exported = True
        self._save()

    # --- Interaction protocol (called by the phase tools) ---

    async def ask_user(
        self, question: str, context: str, options: list[OptionSpec], recommended: str | None
    ) -> str:
        answer = await self.host.questions.ask(
            EventType.QUESTION_ASKED,
            {
                "question": question,
                "context": context,
                "recommended": recommended,
                "options": [o.model_dump() for o in options],
            },
        )
        chosen = answer.choice or ""
        result = (
            f"The user chose: {chosen}" + (f". They added: {answer.text}" if answer.text else "")
            if chosen
            else f"The user answered: {answer.text or '(no answer)'}"
        )
        self.store.append_log(
            "DISCUSSIONS.md",
            f"**{question}**\n{context}\nOptions: "
            + ", ".join(o.label for o in options)
            + f"\nRecommended: {recommended}\n{result}",
        )
        if chosen:
            self.store.append_log(
                "DECISIONS.md", f"{question} → {chosen}" + (f" ({answer.text})" if answer.text else "")
            )
        return result

    async def propose_requirements(self, markdown: str) -> ToolResult:
        """Optional (D-128): writes REQUIREMENTS.md for the record. Not a turn-blocking approval gate —
        Forge can keep working without calling this at all for a small requirement."""
        self.store.write_document("REQUIREMENTS.md", markdown)
        self._refresh_pinned()
        return ToolResult(ok=True, content="Saved REQUIREMENTS.md.")

    async def approve_profile_change(self, document: str, markdown: str, change: str) -> tuple[bool, str]:
        """Mode B: every host-profile change is shown to the user first (spec §6A.2)."""
        return await self._approve("profile", f"Update the host profile ({document})? {change}", markdown)

    async def propose_plan(self, markdown: str, tasks: list[TaskSpec]) -> ToolResult:
        """Optional (D-128): writes PLAN.md and sets the task list. Not a turn-blocking approval gate —
        used when Forge judges a written plan is worth having (a real design fork, or a larger requirement),
        or when the user asks to see one first."""
        if self.workspace.mode_b:  # surface the assumptions at plan approval (spec §6A.2)
            open_assumptions = AssumptionRegister(self.workspace).summary_for_plan()
            if open_assumptions and open_assumptions not in markdown:
                markdown = f"{markdown}\n\n## {open_assumptions}"
        self.store.write_document("PLAN.md", markdown)
        kept = [t for t in self.state.tasks if t.status == "done"]
        # A change request's plan often reuses T1, T2…: rename those so finished tasks stay finished and
        # the new ones still run (dropping them silently made a restructure do nothing).
        self.state.tasks = kept + _renumbered(
            [Task(**spec.model_dump()) for spec in tasks], {t.id for t in kept}
        )
        self._refresh_pinned()
        self._save()
        # Tasks now exist but current_task is still unset (or stale): without ending the turn here, the
        # model can keep calling tools indefinitely and _run_agent's loop never gets a chance to call
        # _start_task, so current_task stays None all session and every task_update is rejected (seen
        # live: a whole small project built in one turn, then blocked at the end with nothing to show
        # for it on the task board). Ending the turn lets the orchestrator start the first pending task
        # before the model's next reply, the same way a successful task_update already does.
        self.context.end_turn = True
        return ToolResult(ok=True, content=f"Saved PLAN.md with {len(tasks)} task(s). Work on them now.")

    async def update_plan(self, markdown: str, tasks: list[TaskSpec], reason: str) -> ToolResult:
        status = {t.id: t for t in self.state.tasks}
        self.store.write_document("PLAN.md", markdown)
        self.state.tasks = [
            status[s.id] if s.id in status and status[s.id].status == "done" else Task(**s.model_dump())
            for s in tasks
        ]
        # The current task may have been renamed, reshuffled, or dropped by this update: it's no longer
        # trustworthy as "the task in progress" until _run_agent re-derives it from the new list. Clearing
        # it here (rather than leaving a stale id) avoids task_update later rejecting a call against a task
        # id that no longer means what it did, or silently reattaching to the wrong task of the same id.
        if self.state.current_task not in {t.id for t in self.state.tasks}:
            self.state.current_task = None
        self._refresh_pinned()
        self._save()
        # See propose_plan: without ending the turn, _run_agent's loop never regains control to call
        # _start_task on the (possibly new) current task, and the model can keep working indefinitely
        # with no task ever marked in_progress.
        self.context.end_turn = True
        return ToolResult(ok=True, content=f"Plan updated ({reason}).")

    async def task_update(
        self,
        task_id: str,
        status: str,
        handoff_note: str,
        verification: str,
        blocked_reason: str,
        context: ToolContext,
    ) -> ToolResult:
        task = self.state.task(task_id)
        if task is None or task.id != self.state.current_task:
            return ToolResult(
                ok=False, content=f"The current task is {self.state.current_task}, not {task_id}."
            )
        edited = context.last_edit_step > self._task_start_step
        if status == "done" and edited and context.last_verified_step <= context.last_edit_step:
            return ToolResult(
                ok=False,
                content=(
                    "Not accepted: no passing test run since your last edit. Run the tests with "
                    "run_command (e.g. python -m pytest) and call task_update again when they pass. If "
                    "there are no tests for this code yet, write them now as part of this task (in the "
                    "project's test style): a task without a passing test isn't done, and it isn't "
                    "blocked either."
                ),
            )
        task.status = "done" if status == "done" else "blocked"
        task.handoff_note, task.verification, task.blocked_reason = handoff_note, verification, blocked_reason
        if task.status == "done":  # local history (spec §13B): one commit per completed task
            await asyncio.to_thread(History(self.workspace).commit, f"{task.id}: {task.title}")
        self.state.current_task = None
        self.store.append_log(
            "PROGRESS.md", f"{task.id} {task.title}: {task.status}. {verification}\n{handoff_note}"
        )
        self.context.end_turn = True
        self._save()
        await self._notice(
            "task", f"{task.id} {task.status}: {task.title}" + (f" — {verification}" if verification else "")
        )
        return ToolResult(ok=True, content=f"Task {task.id} recorded as {task.status}.")

    async def request_user_action(
        self, title: str, steps: list[str], verify_command: str | None, context: ToolContext
    ) -> ToolResult:
        answer = await self.host.questions.ask(
            EventType.USER_ACTION_REQUESTED,
            {"title": title, "steps": steps, "verify_command": verify_command},
        )
        choice = (answer.choice or "").lower()
        if choice == "done" and verify_command:
            result = await execute(context, verify_command, 120, None)
            return ToolResult(
                ok=result.ok, content=f"The user says it's done. Verification: {result.content}"
            )
        if choice == "cant":
            return ToolResult(
                ok=True,
                content=f"The user can't do this ({answer.text or 'no reason given'}). Propose a "
                "workaround or a code change with ask_user, or mark the task blocked.",
            )
        return ToolResult(
            ok=True, content=f"The user answered: {choice or 'skip'}. {answer.text or ''}".strip()
        )

    # --- cadence (D-130, D-132) ---

    def set_cadence(self, cadence: Cadence) -> None:
        """Sets and persists the cadence (D-132) — called when the user says so in chat (detect_cadence),
        or by a headless run's --auto-approve (spec §8, A-9: still never covers the always-ask list)."""
        self.state.cadence = cadence
        self._apply_cadence()
        self._save()

    def _apply_cadence(self) -> None:
        """Maps the persisted cadence onto the permission gate's mode (§14.2). Free hand runs everything
        except the always-ask/critical list; ask-every-step tightens to 'default' (confirm before writes);
        the default cadence leaves the gate at whatever mode the session already has."""
        agent = self.host.agent
        if agent is None:
            return
        if self.state.cadence == "free_hand":
            agent.gate.mode = "auto"
        elif self.state.cadence == "ask_every_step":
            agent.gate.mode = "default"

    # --- misc helpers ---

    async def _approve(self, kind: str, summary: str, markdown: str) -> tuple[bool, str]:
        answer = await self.host.approvals.request(
            {
                "tool": f"propose_{kind}",
                "kind": kind,
                "summary": summary,
                "markdown": markdown,
                "reason": f"{kind} approval",
            }
        )
        return answer.approved, answer.instruction or "no details given"

    def _start_change(self, text: str, restructure: bool) -> None:
        if not restructure:
            self.state.requirement = f"{self.state.requirement}\n\nChange request: {text}"
        self.state.change_request = text
        self.state.restructuring = restructure
        self.state.exported = False
        self.host.history.append(Message.system(self._format("restructure" if restructure else "change")))

    def _format(self, kind: str, **values: str) -> str:
        defaults = {
            "requirement": self._requirement_text(),
            "explore_notes": self.state.explore_notes or "(none)",
            "task": "",
            "task_board": self.state.task_board(),
            "test_command": "the project's own test command (e.g. python -m pytest) run with run_command",
        }
        return self.instructions[kind].format(**{**defaults, **values})

    def _requirement_text(self) -> str:
        approved = self.workspace.forge_dir / "REQUIREMENTS.md"
        return approved.read_text(encoding="utf-8") if approved.exists() else self.state.requirement

    def _task_text(self, task: Task) -> str:
        return (
            f"{task.id}: {task.title}\n{task.description}\nDone when: {task.acceptance or 'its tests pass'}"
        )

    def _save(self) -> None:
        self.store.save(self.state)
        self._refresh_pinned()
        self._publish_tasks()

    def _publish_tasks(self) -> None:
        """task_list_updated for the UIs (spec §15A.2); _save is synchronous, so the publish is scheduled."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        payload = {
            "current_task": self.state.current_task,
            "cadence": self.state.cadence,
            "tasks": [t.model_dump() for t in self.state.tasks],
            # Lets the Run map show a "delivered" node without relying on the stale phase field (D-133).
            "exported": self.state.exported,
        }
        task = loop.create_task(self.host.bus.publish(EventType.TASK_LIST_UPDATED, payload))
        self._publishing.add(task)
        task.add_done_callback(self._publishing.discard)

    def _refresh_pinned(self) -> None:
        pinned = self.host.context_manager.pinned
        pinned.set("requirement", self._requirement_text() or None)
        current = self.state.task(self.state.current_task) if self.state.current_task else None
        pinned.set(
            "phase_and_tasks",
            (f"Current task: {current.id} {current.title}\n" if current else "") + self.state.task_board(),
        )

    def _background(self, task: asyncio.Task[Any]) -> None:
        """Runs a task (e.g. the retro) alongside the input loop instead of inside a turn, so it can never
        block the user's next message. Errors are reported as a notice rather than propagating unseen."""
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def wait_idle(self) -> None:
        """Lets a caller (headless run, shutdown) observe the settled state after background work like the
        retro finishes, without making the user's own turn wait for it."""
        while self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)

    async def _notice(self, kind: str, text: str) -> None:
        await self.host.bus.publish(EventType.NOTICE, {"kind": kind, "text": text})

    async def _run_tests(self) -> tuple[bool, str]:
        """The full suite from the app folder (whatever directory the model last changed into), parsed."""
        shell = self.context.shell
        python = (shell.python if shell else None) or "python"
        result = await execute(
            self.context,
            f"& {ps_quote(python)} -m pytest {PYTEST_ARGS}",
            FULL_SUITE_TIMEOUT_S,
            self.workspace.info.app_subfolder or None,
        )
        report = parse_pytest(result.content)
        if report.ran:
            return report.passed, report.summary()[-4000:]
        return result.ok, result.content[-1500:]


def _unique_id(wanted: str, taken: set[str]) -> str:
    if wanted not in taken:
        return wanted
    stem = wanted.rstrip("0123456789") or wanted
    number = 2
    while f"{stem}{number}" in taken:
        number += 1
    return f"{stem}{number}"


def _renumbered(tasks: list[Task], taken: set[str]) -> list[Task]:
    """New tasks get ids unique against `taken` (and each other); depends_on follows the renames."""
    renames: dict[str, str] = {}
    used = set(taken)
    for task in tasks:
        new_id = task.id if task.id not in used else _unique_id(f"C{task.id}", used)
        renames[task.id] = new_id
        used.add(new_id)
    for task in tasks:
        task.id = renames[task.id]
        task.depends_on = [renames.get(d, d) for d in task.depends_on]
    return tasks
