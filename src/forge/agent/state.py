"""Persistent orchestrator state (spec §7, §12.6): phase, tasks, approvals — everything needed to resume.

Stored in <workspace>/.forge/state.json and rewritten after every transition, so a killed run resumes at
the same phase and task. Human-readable companions live next to it: REQUIREMENTS.md, PLAN.md, tasks.json,
PROGRESS.md, DECISIONS.md, DISCUSSIONS.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from forge.workspace.workspace import Workspace


class Phase(StrEnum):
    INTAKE = "intake"
    CLARIFY = "clarify"
    KB_CHECK = "kb_check"
    EXPLORE = "explore"
    PLAN = "plan"
    EXECUTE = "execute"
    REVIEW = "review"
    EXPORT = "export"
    HANDOFF = "handoff"
    RESTRUCTURE = "restructure"
    DONE = "done"


TaskStatus = Literal["pending", "in_progress", "done", "blocked"]


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
    phase: Phase = Phase.INTAKE
    requirement: str = ""
    requirements_approved: bool = False
    plan_approved: bool = False
    tasks: list[Task] = Field(default_factory=list)
    current_task: str | None = None
    explore_notes: str = ""
    change_request: str = ""  # set while a change request or restructure is being planned/executed
    restructuring: bool = False
    clarify_rounds: int = 0
    updated: str = ""

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
