from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models import Task

MAX_HISTORY = 20


class TaskStore:
    """A list of tasks kept in memory and, when a path is given, in a JSON file, with undo and redo."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.tasks: list[Task] = []
        self._next_id = 1
        self._undo: list[dict[str, Any]] = []
        self._redo: list[dict[str, Any]] = []
        if path is not None and path.exists():
            self._load()

    def add(self, title: str) -> Task:
        title = title.strip()
        if not title:
            raise ValueError("a task needs a title")
        self._checkpoint()
        task = Task(id=self._next_id, title=title)
        self._next_id += 1
        self.tasks.append(task)
        self._save()
        return task

    def complete(self, task_id: int) -> Task:
        task = self._find(task_id)
        if task.done:
            return task
        self._checkpoint()
        task.done = True
        self._save()
        return task

    def remove(self, task_id: int) -> None:
        task = self._find(task_id)
        self._checkpoint()
        self.tasks.remove(task)
        self._save()

    def list(self, include_done: bool = True) -> list[Task]:
        return [t for t in self.tasks if include_done or not t.done]

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self._snapshot())
        self._restore(self._undo.pop())
        self._save()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self._snapshot())
        self._restore(self._redo.pop())
        self._save()
        return True

    def _snapshot(self) -> dict[str, Any]:
        return {"next_id": self._next_id, "tasks": [t.to_dict() for t in self.tasks]}

    def _restore(self, snapshot: dict[str, Any]) -> None:
        self._next_id = int(snapshot["next_id"])
        self.tasks = [Task.from_dict(item) for item in snapshot["tasks"]]

    def _checkpoint(self) -> None:
        """Called before a change: remember the state so it can be undone, and forget the redo history."""
        self._undo.append(self._snapshot())
        del self._undo[:-MAX_HISTORY]
        self._redo.clear()

    def _find(self, task_id: int) -> Task:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(task_id)

    def _save(self) -> None:
        if self.path is None:
            return
        data = {**self._snapshot(), "history": {"undo": self._undo, "redo": self._redo}}
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load(self) -> None:
        assert self.path is not None
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self._restore(data)
        history = data.get("history") or {}
        self._undo = list(history.get("undo", []))[-MAX_HISTORY:]
        self._redo = list(history.get("redo", []))
