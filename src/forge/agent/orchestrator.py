"""The requirement workflow (spec §7): CLARIFY -> KB CHECK -> EXPLORE -> PLAN -> [approve] -> EXECUTE (task by
task) -> REVIEW -> EXPORT -> HANDOFF, plus change requests and RESTRUCTURE (§6.7).

The engine drives the phases, not the model: each phase runs the agent loop with its own tools and
instructions, and ends only when its phase tool succeeds (propose_requirements / propose_plan approved,
task_update). State is saved after every transition, so a killed run resumes where it stopped.
"""

from __future__ import annotations

import asyncio
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

from forge.agent.learning_hooks import after_export, pin_lessons, related_cards_note
from forge.agent.reports import closing_message, final_report
from forge.agent.review import run_reviewer
from forge.agent.state import Phase, StateStore, Task
from forge.agent.subagent import run_explore
from forge.config import forge_home
from forge.engine.events import EventType
from forge.kb.builder import build as kb_build
from forge.kb.builder import status as kb_status
from forge.kb.narrative import llm_writer
from forge.learning.improve import prompt_override
from forge.llm.base import Message
from forge.modeb.assumptions import AssumptionRegister
from forge.modeb.fixture_check import check_fixture_use
from forge.modeb.output import build_modeb_output
from forge.parity.history import History
from forge.tools.base import Tool, ToolContext, ToolResult
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
from forge.tools.shell import execute
from forge.verify.ladder import VerifyLadder
from forge.verify.test_guard import check_stubs, check_tests
from forge.workspace.output import build_output

if TYPE_CHECKING:
    from forge.engine.session_host import SessionHost

MAX_NUDGES = 1
MAX_REVIEW_FIX_ROUNDS = 2
RESUMED_NOTE = (
    "\n\nResumed after an interruption: first check what is already done (files modified are pinned)."
)
NUDGE = (
    "Finish the current step: verify and call task_update, or ask the user if you are blocked. "
    "Don't stop without one of these."
)


def phase_instructions() -> dict[str, str]:
    text = resources.files("forge").joinpath("agent/prompts/phases.md").read_text(encoding="utf-8")
    override = prompt_override(forge_home(), "phases")  # approved tier-2 tweaks (spec §12.5)
    sections: dict[str, str] = {}
    for block in text.split("\n## ")[1:]:
        name, _, body = block.partition("\n")
        sections[name.strip()] = body.strip() + (
            f"\n\n{override.replace('{', '{{').replace('}', '}}')}" if override else ""
        )
    return sections


class Orchestrator:
    def __init__(self, host: SessionHost) -> None:
        assert host.workspace is not None and host.agent is not None
        self.host = host
        self.workspace = host.workspace
        self.store = StateStore(self.workspace)
        self.state = self.store.load()
        self.instructions = phase_instructions()
        self.context: ToolContext = host.agent.context
        self.context.interaction = self
        self._task_start_step = 0
        self._baseline_tests: tuple[bool, str] | None = None
        self._review_rounds = 0
        self._publishing: set[asyncio.Task[Any]] = set()
        self._refresh_pinned()

    # --- entry points ---

    @property
    def needs_resume(self) -> bool:
        return self.state.phase not in (Phase.INTAKE, Phase.DONE, Phase.HANDOFF)

    async def handle_message(self, text: str) -> None:
        if self.state.phase in (Phase.INTAKE,):
            self.state.requirement = text
            self._enter(Phase.CLARIFY)
        elif self.state.phase in (Phase.DONE, Phase.HANDOFF):
            self._start_change(text, restructure=False)
        else:
            self.host.history.append(Message.user(text))
        await self.advance()

    async def resume(self) -> None:
        await self._notice(
            "resume",
            f"Resuming at phase {self.state.phase.value}"
            + (f", task {self.state.current_task}" if self.state.current_task else "")
            + ".",
        )
        await self.host.prepare_database()
        if self.state.phase == Phase.EXECUTE and self.state.current_task:
            self._start_task(self.state.task(self.state.current_task), resumed=True)  # type: ignore[arg-type]
        await self.advance()

    async def restructure(self, instruction: str) -> None:
        passed, summary = await self._run_tests()
        self._baseline_tests = (passed, summary)
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
        if waiting and self.state.phase in (Phase.REVIEW, Phase.EXPORT, Phase.DONE):
            self.state.phase = Phase.EXECUTE
        self._save()
        return bool(waiting)

    # --- the phase machine ---

    async def advance(self) -> None:
        while True:
            phase = self.state.phase
            if phase == Phase.CLARIFY:
                if not await self._conversation_phase(
                    "clarify", self._planning_tools(ProposeRequirements()), "plan"
                ):
                    return
                self._enter(Phase.KB_CHECK)
            elif phase == Phase.KB_CHECK:
                if not self.workspace.mode_b:  # Mode B has a host profile instead of a KB (spec §6A.5)
                    await self._kb_check()
                await self.host.prepare_database()
                self._enter(Phase.EXPLORE)
            elif phase == Phase.EXPLORE and self.workspace.mode_b:
                self.state.explore_notes = (
                    "Mode B: there is no repository to explore. Use the pinned host profile, profile_search "
                    "and profile_read; ask the user for gaps."
                )
                self._enter(Phase.PLAN)
            elif phase == Phase.EXPLORE:
                await self._notice("explore", "Exploring the codebase for this requirement…")
                self.state.explore_notes = await run_explore(
                    self.host.router, self.context, self._requirement_text()
                )
                self.store.write_document("notes/explore.md", self.state.explore_notes)
                self._enter(Phase.PLAN)
            elif phase in (Phase.PLAN, Phase.RESTRUCTURE):
                if not await self._conversation_phase(
                    self._plan_kind(), self._planning_tools(ProposePlan()), "plan"
                ):
                    return
                self._enter(Phase.EXECUTE)
            elif phase == Phase.EXECUTE:
                if not await self._execute_tasks():
                    return
                self._enter(Phase.REVIEW)
            elif phase == Phase.REVIEW:
                if await self._review():
                    self._enter(Phase.EXPORT)
                else:
                    self._enter(Phase.EXECUTE)
            elif phase == Phase.EXPORT:
                await self._export()
                self.state.change_request, self.state.restructuring = "", False
                await after_export(self)  # library card, metrics, RETRO (spec §12)
                self._enter(Phase.DONE)
            else:
                return

    async def _conversation_phase(self, kind: str, tools: ToolRegistry, mode: str) -> bool:
        """Runs a talking phase until its phase tool succeeds (True) or the model waits for the user
        (False)."""
        if not self._phase_started(kind):
            values = {"requirement": self.state.change_request} if kind in ("change", "restructure") else {}
            text = self._format(kind, **values)
            if kind in ("plan", "change"):
                text += related_cards_note(self)  # the library: earlier requirements to reuse and cite
            self.host.history.append(Message.system(text))
        return await self._run_agent(tools, mode)

    async def _execute_tasks(self) -> bool:
        while (task := self.state.next_task()) is not None:
            if self.state.current_task != task.id or task.status != "in_progress":
                self._start_task(task)
            if not await self._run_agent(self._execution_tools(), "default"):
                return False
        return True

    async def _run_agent(self, tools: ToolRegistry, mode: str) -> bool:
        agent = self.host.agent
        assert agent is not None
        agent.tools = tools
        previous_mode = agent.gate.mode
        if mode == "plan":
            agent.gate.mode = "plan"
        self.context.end_turn = False
        try:
            for nudge in range(MAX_NUDGES + 1):
                await agent.run(self.host.history, self.host.stream_delta)
                if self.context.end_turn:
                    return True
                if self.state.phase != Phase.EXECUTE or nudge == MAX_NUDGES:
                    return False  # waiting for the user's reply
                self.host.history.append(Message.system(NUDGE))
            return False
        finally:
            self.context.end_turn = False
            agent.gate.mode = previous_mode
            self._save()

    # --- phases ---

    async def _kb_check(self) -> None:
        kb_dir = self.host.kb_dir()
        assert kb_dir is not None
        repo, app = Path(self.workspace.info.repo_path), self.workspace.info.app_subfolder
        changes = kb_status(repo, app, kb_dir)
        if changes is not None and not changes.all:
            return
        await self._notice(
            "kb",
            "Building the knowledge base…"
            if changes is None
            else f"Refreshing the knowledge base ({len(changes.all)} changed file(s))…",
        )
        await kb_build(repo, app, kb_dir, llm_writer(self.host.router))
        self.host.reload_kb()

    def _start_task(self, task: Task, resumed: bool = False) -> None:
        previous = [t for t in self.state.tasks if t.status == "done"]
        handoff = previous[-1].handoff_note if previous else None
        task.status = "in_progress"
        task.attempts += 1
        self.state.current_task = task.id
        brief = self._format("execute", task=self._task_text(task))
        if resumed:
            brief += RESUMED_NOTE
        self.host.context_manager.reset_for_task(self.host.history, brief, handoff)
        pin_lessons(self, self._task_text(task))
        self._task_start_step = self.context.step
        if self.host.agent is not None:
            self.host.agent.stuck.reset()
            self.host.agent.escalator.reset()
        self._save()

    async def _review(self) -> bool:
        """Spec §13: the full suite, then — when it passes — the test guard (weakened tests) and the reviewer
        subagent. Failures or blocking findings become one fix task (bounded rounds)."""
        passed, summary = await self._run_tests()
        report = [f"# Review\n\nFull test suite: {'PASSED' if passed else 'FAILED'}\n\n```\n{summary}\n```\n"]
        if self._baseline_tests is not None:
            same = self._baseline_tests[0] == passed
            report.append(
                f"\nRestructure check — tests before: {'PASSED' if self._baseline_tests[0] else 'FAILED'}; "
                f"after: {'PASSED' if passed else 'FAILED'} ({'same' if same else 'DIFFERENT'}).\n"
            )
        problems: list[str] = []
        if passed:
            guard = (
                check_tests(self.workspace) + check_stubs(self.workspace) + check_fixture_use(self.workspace)
            )
            report.append(
                "\n## Test guard\n\n" + ("\n".join(f"- {g.render()}" for g in guard) or "No weakened tests.")
            )
            problems += [g.render() for g in guard if g.blocking]
            await self._notice("review", "Tests pass; the reviewer is reading the change…")
            review = await run_reviewer(self.host.router, self.context, self._requirement_text())
            if review is not None:
                report.append("\n## Reviewer\n\n" + review.report)
                problems += [f.render() for f in review.blocking]
        self.store.write_document("reports/review.md", "\n".join(report))
        if (passed and not problems) or self._review_rounds >= MAX_REVIEW_FIX_ROUNDS:
            outcome = "passed" if passed and not problems else "has open findings — reported"
            await self._notice("review", f"Review {outcome}.")
            self._baseline_tests = None if passed else self._baseline_tests
            return True
        self._review_rounds += 1
        if not passed:
            title, detail = (
                "Fix the failing tests from the full-suite run",
                f"The full test suite failed:\n{summary}",
            )
        else:
            title = "Address the review findings"
            detail = "Review findings to fix (blocking):\n" + "\n".join(f"- {p}" for p in problems)
        fix = Task(
            id=_unique_id("FIX1", {t.id for t in self.state.tasks}),
            title=title,
            description=detail[-4000:],
            acceptance="The full test suite passes and the findings are resolved (tests are never weakened).",
        )
        self.state.tasks.append(fix)
        await self._notice("review", f"{title}: added task {fix.id}.")
        return False

    def block_current_task(self, reason: str) -> None:
        """Escalation's last step (spec §13.3): the task is blocked and work moves on."""
        task = self.state.task(self.state.current_task) if self.state.current_task else None
        if task is not None:
            task.status, task.blocked_reason = "blocked", reason
            self.state.current_task = None
            self.store.append_log("PROGRESS.md", f"- {task.id} blocked: {reason}")
            self._save()

    async def _export(self) -> None:
        output = build_modeb_output(self.workspace) if self.workspace.mode_b else build_output(self.workspace)
        report = final_report(self.state, self._requirement_text(), output, self.workspace, self.host.db)
        self.store.write_document("reports/final.md", report)
        await self.host.bus.publish(
            EventType.MESSAGE_DONE, {"text": closing_message(self.state, output), "model": "forge"}
        )

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
        answer = await self._approve("requirements", "Approve REQUIREMENTS.md?", markdown)
        if not answer[0]:
            return ToolResult(
                ok=True, content=f"The user requested changes: {answer[1]}. Revise and propose again."
            )
        self.store.write_document("REQUIREMENTS.md", markdown)
        self.state.requirements_approved = True
        self.context.end_turn = True
        self._refresh_pinned()
        return ToolResult(ok=True, content="Requirements approved.")

    async def approve_profile_change(self, document: str, markdown: str, change: str) -> tuple[bool, str]:
        """Mode B: every host-profile change is shown to the user first (spec §6A.2)."""
        return await self._approve("profile", f"Update the host profile ({document})? {change}", markdown)

    async def propose_plan(self, markdown: str, tasks: list[TaskSpec]) -> ToolResult:
        if self.workspace.mode_b:  # surface the assumptions at plan approval (spec §6A.2)
            open_assumptions = AssumptionRegister(self.workspace).summary_for_plan()
            if open_assumptions and open_assumptions not in markdown:
                markdown = f"{markdown}\n\n## {open_assumptions}"
        approved, feedback = await self._approve("plan", f"Approve PLAN.md ({len(tasks)} tasks)?", markdown)
        if not approved:
            return ToolResult(
                ok=True, content=f"The user requested changes: {feedback}. Revise and propose again."
            )
        self.store.write_document("PLAN.md", markdown)
        kept = [t for t in self.state.tasks if t.status == "done"]
        # A change request's plan often reuses T1, T2…: rename those so finished tasks stay finished and
        # the new ones still run (dropping them silently made a restructure do nothing).
        self.state.tasks = kept + _renumbered(
            [Task(**spec.model_dump()) for spec in tasks], {t.id for t in kept}
        )
        self.state.plan_approved = True
        self.context.end_turn = True
        self._refresh_pinned()
        return ToolResult(ok=True, content="Plan approved. Implementation starts now, task by task.")

    async def update_plan(self, markdown: str, tasks: list[TaskSpec], reason: str) -> ToolResult:
        approved, feedback = await self._approve(
            "plan", f"Approve the changed plan? Reason: {reason}", markdown
        )
        if not approved:
            return ToolResult(ok=True, content=f"The user rejected the change: {feedback}")
        status = {t.id: t for t in self.state.tasks}
        self.store.write_document("PLAN.md", markdown)
        self.state.tasks = [
            status[s.id] if s.id in status and status[s.id].status == "done" else Task(**s.model_dump())
            for s in tasks
        ]
        self._refresh_pinned()
        self._save()
        return ToolResult(ok=True, content="The updated plan is approved.")

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
                    "Not accepted: no passing test run since your last edit. Run the tests "
                    "(verify or run_tests) and call task_update again when they pass. If there are no "
                    "tests for this code yet, write them now as part of this task (in the project's "
                    "test style): a task without a passing test isn't done, and it isn't blocked either."
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

    # --- helpers ---

    async def _approve(self, kind: str, summary: str, markdown: str) -> tuple[bool, str]:
        answer = await self.host.approvals.request(
            {
                "tool": f"propose_{kind}",
                "kind": kind,
                "summary": summary,
                "markdown": markdown,
                "reason": f"{kind} approval gate",
            }
        )
        return answer.approved, answer.instruction or "no details given"

    def _start_change(self, text: str, restructure: bool) -> None:
        if not restructure:
            self.state.requirement = f"{self.state.requirement}\n\nChange request: {text}"
        self.state.plan_approved = False
        self.state.change_request = text
        self.state.restructuring = restructure
        self._review_rounds = 0
        self._enter(Phase.RESTRUCTURE if restructure else Phase.PLAN)

    def _plan_kind(self) -> str:
        if self.state.restructuring:
            return "restructure"
        return "change" if self.state.change_request else "plan"

    def _phase_started(self, kind: str) -> bool:
        marker = self.instructions[kind][:40]
        return any(m.role == "system" and m.content.startswith(marker) for m in self.host.history)

    def _planning_tools(self, phase_tool: object) -> ToolRegistry:
        read_only = [t for t in [*default_tools(), *self._db_tools(), *self.host.extra_tools] if t.read_only]
        return ToolRegistry([*read_only, AskUser(), phase_tool])  # type: ignore[list-item]

    def _execution_tools(self) -> ToolRegistry:
        return ToolRegistry(
            [
                *default_tools(),
                *self._db_tools(),
                *self.host.extra_tools,  # Mode B profile/contract tools, MCP server tools
                AskUser(),
                TaskUpdate(),
                UpdatePlan(),
                RequestUserAction(),
            ]
        )

    def _db_tools(self) -> list[Tool]:
        return db_tools() if self.host.db is not None else []

    def _format(self, kind: str, **values: str) -> str:
        defaults = {
            "requirement": self._requirement_text(),
            "explore_notes": self.state.explore_notes or "(none)",
            "task": "",
            "task_board": self.state.task_board(),
            "test_command": "the verify tool; run_tests for specific tests",
        }
        return self.instructions[kind].format(**{**defaults, **values})

    def _requirement_text(self) -> str:
        approved = self.workspace.forge_dir / "REQUIREMENTS.md"
        return approved.read_text(encoding="utf-8") if approved.exists() else self.state.requirement

    def _task_text(self, task: Task) -> str:
        return (
            f"{task.id}: {task.title}\n{task.description}\nDone when: {task.acceptance or 'its tests pass'}"
        )

    def _enter(self, phase: Phase) -> None:
        self.state.phase = phase
        self._save()

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
            "phase": self.state.phase.value,
            "current_task": self.state.current_task,
            "tasks": [t.model_dump() for t in self.state.tasks],
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
            f"Phase: {self.state.phase.value}\n"
            + (f"Current task: {current.id} {current.title}\n" if current else "")
            + self.state.task_board(),
        )

    async def _notice(self, kind: str, text: str) -> None:
        await self.host.bus.publish(EventType.NOTICE, {"kind": kind, "text": text})

    async def _run_tests(self) -> tuple[bool, str]:
        """The full suite from the app folder (whatever directory the model last changed into), parsed."""
        step, _ = await VerifyLadder(self.context).run_tests("")
        return step.ok, step.summary[-4000:]


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
