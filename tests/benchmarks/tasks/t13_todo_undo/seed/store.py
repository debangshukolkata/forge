from __future__ import annotations

import json
from pathlib import Path

from models import Task


class TaskStore:
    """A list of tasks kept in memory and, when a path is given, in a JSON file."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.tasks: list[Task] = []
        self._next_id = 1
        if path is not None and path.exists():
            self._load()

    def add(self, title: str) -> Task:
        title = title.strip()
        if not title:
            raise ValueError("a task needs a title")
        task = Task(id=self._next_id, title=title)
        self._next_id += 1
        self.tasks.append(task)
        self._save()
        return task

    def complete(self, task_id: int) -> Task:
        task = self._find(task_id)
        task.done = True
        self._save()
        return task

    def remove(self, task_id: int) -> None:
        task = self._find(task_id)
        self.tasks.remove(task)
        self._save()

    def list(self, include_done: bool = True) -> list[Task]:
        return [t for t in self.tasks if include_done or not t.done]

    def _find(self, task_id: int) -> Task:
        for task in self.tasks:
            if task.id == task_id:
                return task
        raise KeyError(task_id)

    def _save(self) -> None:
        if self.path is None:
            return
        data = {"next_id": self._next_id, "tasks": [t.to_dict() for t in self.tasks]}
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load(self) -> None:
        assert self.path is not None
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self._next_id = int(data["next_id"])
        self.tasks = [Task.from_dict(item) for item in data["tasks"]]
