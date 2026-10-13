"""Which planned tasks may run at the same time (TODO X7, D-306). Pure logic over the task list, no I/O.

A task may run in parallel only when the plan says where it writes (`folder`) and the scheduler can prove it is independent of the
others in the same batch:
- all the tasks it depends on are done (the frontier);
- its folder is not the same as, nor inside, nor around another batch member's folder;
- it names no `resource` another batch member names (a resource is anything exclusive: a port, a database schema, a root
  package.json, a lock file, a shared component);
- the batch has room (`limit`).
Everything else waits or runs one after the other, and the scheduler says why (the main agent reads the reasons and may fix the plan).
A dependency cycle or an unknown dependency makes the affected tasks serial. When in doubt, serial."""

from __future__ import annotations

from dataclasses import dataclass, field

from forge.toolkit.folders import clean_folder, folders_disjoint
from forge.workflow.state import Task


@dataclass
class Batch:
    run: list[Task] = field(default_factory=list)  # may start together
    held: list[tuple[Task, str]] = field(
        default_factory=list
    )  # ready, but not in this batch, with the reason

    @property
    def parallel(self) -> bool:
        return len(self.run) >= 2


def dependency_problems(tasks: list[Task]) -> dict[str, str]:
    """Task id -> why its dependencies cannot be trusted (an unknown id, or part of a cycle)."""
    ids = {t.id for t in tasks}
    problems: dict[str, str] = {}
    for task in tasks:
        missing = [d for d in task.depends_on if d not in ids]
        if missing:
            problems[task.id] = f"depends on unknown task {', '.join(missing)}"
    by_id = {t.id: t for t in tasks}

    def reaches(start: str, target: str, seen: set[str]) -> bool:
        for dep in by_id[start].depends_on:
            if dep == target:
                return True
            if dep in by_id and dep not in seen:
                seen.add(dep)
                if reaches(dep, target, seen):
                    return True
        return False

    for task in tasks:
        if task.id not in problems and reaches(task.id, task.id, set()):
            problems[task.id] = "is part of a dependency cycle"
    return problems


def frontier(tasks: list[Task]) -> list[Task]:
    """Pending tasks whose dependencies are all done and trustworthy."""
    done = {t.id for t in tasks if t.status == "done"}
    broken = dependency_problems(tasks)
    return [
        t
        for t in tasks
        if t.status == "pending" and t.id not in broken and all(d in done for d in t.depends_on)
    ]


def plan_batch(tasks: list[Task], limit: int, only: set[str] | None = None) -> Batch:
    """The tasks of the frontier that can start together (at most `limit`), and why each other ready task is held back."""
    batch = Batch()
    for task in frontier(tasks):
        if only is not None and task.id not in only:
            continue
        reason = _conflict(task, batch.run, limit)
        if reason is None:
            batch.run.append(task)
        else:
            batch.held.append((task, reason))
    return batch


def _conflict(task: Task, chosen: list[Task], limit: int) -> str | None:
    if not clean_folder(task.folder):
        return "has no folder (a task that does not say where it writes runs alone)"
    if len(chosen) >= limit:
        return f"the limit of {limit} parallel builders is reached"
    for other in chosen:
        if not folders_disjoint(task.folder, other.folder):
            return f"its folder {task.folder!r} overlaps {other.id}'s folder {other.folder!r}"
        shared = sorted(set(task.resources) & set(other.resources))
        if shared:
            return f"shares {', '.join(shared)} with {other.id}"
    return None


def explain(tasks: list[Task], batch: Batch, limit: int) -> str:
    """Text for the main agent when a batch is not worth starting: what is ready, what is held back and why."""
    ready = frontier(tasks)
    lines: list[str] = []
    if limit < 2:
        lines.append(
            "Parallel builders are switched off (limits.max_parallel_builders is below 2): work through the tasks one by one."
        )
    elif not ready:
        lines.append("No task is ready: every pending task waits for one that is not done yet.")
    else:
        lines.append(f"Only {len(batch.run)} task(s) can start now.")
    for task, reason in batch.held:
        lines.append(f"- {task.id} {task.title}: {reason}")
    for task_id, why in dependency_problems(tasks).items():
        lines.append(f"- {task_id}: {why} (it runs alone)")
    return "\n".join(lines)
