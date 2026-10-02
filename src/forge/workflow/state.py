"""Persistent orchestrator state (spec §7, §12.6, D-128/D-131/D-132): tasks and cadence — everything needed
to resume. There is no phase field: Forge runs a flat loop, not a fixed phase state machine (D-128, D-131).

Stored in <workspace>/.forge/state.json and rewritten after every change, so a killed run resumes
automatically and silently, the way reopening a conversation with this assistant does — no "resume or
start fresh?" prompt (D-132). Cadence (D-130) is persisted here too, so a "go ahead, don't ask me" grant
survives a crash, a dropped network, or the user returning days later (D-132) — it is still never a config
key, only ever set by the user saying so in chat. Human-readable companions live next to it: REQUIREMENTS.md,
PLAN.md, tasks.json, PROGRESS.md, DECISIONS.md, DISCUSSIONS.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from forge.workspace.workspace import Workspace

TaskStatus = Literal["pending", "in_progress", "done", "blocked"]
Cadence = Literal["default", "free_hand", "ask_every_step"]


class Task(BaseModel):
    id: str
    title: str
    description: str = ""
    acceptance: str = ""  # how to verify it
    depends_on: list[str] = Field(default_factory=list)
    status: TaskStatus = "pending"
    attempts: int = 0
    handoff_note: str = ""  # <= ~200 tokens, carried into the next task (spec §10.6)
    verification: str = ""  # what proved it done
    blocked_reason: str = ""


class OrchestratorState(BaseModel):
    requirement: str = ""
    started: bool = False  # the requirement has been given; distinguishes a fresh workspace from resuming
    exported: bool = False  # output/ has been built at least once; a later message is a change request
    tasks: list[Task] = Field(default_factory=list)
    current_task: str | None = None
    explore_notes: str = ""
    change_request: str = ""  # set while a change request or restructure is being worked on
    restructuring: bool = False
    cadence: Cadence = "default"  # D-130/D-132: persisted, set only by the user saying so in chat
    updated: str = ""

    def resume_summary(self) -> str:
        """A short, honest status for the auto-resume greeting (D-132) — no phase to name, just what's
        actually true: what's pending, what's in progress, and the cadence still in force."""
        if not self.started:
            return "No requirement given yet."
        pending = sum(1 for t in self.tasks if t.status in ("pending", "in_progress"))
        blocked = sum(1 for t in self.tasks if t.status == "blocked")
        done = sum(1 for t in self.tasks if t.status == "done")
        bits = [f"{done} done", f"{pending} pending"]
        if blocked:
            bits.append(f"{blocked} blocked")
        current = f", currently on {self.current_task}" if self.current_task else ""
        cadence_note = "" if self.cadence == "default" else f"; cadence: {self.cadence.replace('_', ' ')}"
        if not self.tasks:
            return f"Understanding the requirement{cadence_note}."
        return f"{', '.join(bits)}{current}{cadence_note}."

    def task(self, task_id: str) -> Task | None:
        return next((t for t in self.tasks if t.id == task_id), None)

    def next_task(self) -> Task | None:
        """The first unfinished task whose dependencies are all done."""
        done = {t.id for t in self.tasks if t.status == "done"}
        for task in self.tasks:
            if task.status in ("pending", "in_progress") and set(task.depends_on) <= done:
                return task
        return None

    def task_board(self) -> str:
        marks = {"pending": "[ ]", "in_progress": "[~]", "done": "[x]", "blocked": "[!]"}
        lines = [
            f"{marks[t.status]} {t.id} {t.title}"
            + (f" (blocked: {t.blocked_reason})" if t.blocked_reason else "")
            for t in self.tasks
        ]
        return "\n".join(lines) or "(no tasks yet)"


class StateStore:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.path = workspace.forge_dir / "state.json"

    def load(self) -> OrchestratorState:
        if not self.path.exists():
            return OrchestratorState()
        return OrchestratorState.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, state: OrchestratorState) -> None:
        state.updated = datetime.now(UTC).isoformat(timespec="seconds")
        target = self.workspace.jail.check(self.path)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(state.model_dump_json(indent=1), encoding="utf-8")
        temporary.replace(target)
        self._write(
            self.workspace.forge_dir / "tasks.json",
            "[\n" + ",\n".join(t.model_dump_json() for t in state.tasks) + "\n]\n",
        )

    def read_document(self, name: str) -> str:
        path = self.workspace.forge_dir / name
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def write_document(self, name: str, text: str) -> Path:
        path = self.workspace.forge_dir / name
        self._write(path, text.rstrip() + "\n")
        return path

    def append_log(self, name: str, entry: str) -> None:
        path = self.workspace.jail.check(self.workspace.forge_dir / name)
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        with path.open("a", encoding="utf-8") as log:
            log.write(f"\n## {stamp}\n{entry.strip()}\n")

    def _write(self, path: Path, text: str) -> None:
        target = self.workspace.jail.check(path)
        target.parent.mkdir(parents=True, exist_ok=True)  # notes/, reports/ ...
        target.write_text(text, encoding="utf-8")
