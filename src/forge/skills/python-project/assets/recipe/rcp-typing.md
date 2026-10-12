---
id: rcp-typing
type: recipe
title: Types that catch bugs
summary: "Dataclasses, Protocol, TypedDict, Literal and Optional handled properly; mypy strict habits."
moods: [robust, clean]
products: [any python code]
tags: [typing, mypy, dataclass, protocol]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-13)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Types that catch bugs

Rules: annotate every function signature (`-> None` too); use `X | None` and handle the `None`; model records as
`@dataclass(frozen=True, slots=True)` (or pydantic models at the edges); depend on behaviour with `Protocol`, not on a
concrete class; `Literal[...]` or `StrEnum` for a fixed set of strings; `TypedDict` only for dictionaries you do not own
(JSON); avoid `Any`; run `python -m mypy` and keep it clean.

```python
# runnable
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class Status(StrEnum):
    OPEN = "open"
    DONE = "done"


@dataclass(frozen=True, slots=True)
class Task:
    title: str
    status: Status = Status.OPEN


class Store(Protocol):
    def save(self, task: Task) -> None: ...


class MemoryStore:
    def __init__(self) -> None:
        self.tasks: list[Task] = []

    def save(self, task: Task) -> None:
        self.tasks.append(task)


def complete(task: Task, store: Store) -> Task:
    finished = Task(task.title, Status.DONE)  # frozen: make a new one instead of mutating
    store.save(finished)
    return finished


def first_word(text: str | None) -> str:
    if text is None:  # mypy forces this branch
        return ""
    return text.split()[0] if text.split() else ""


store = MemoryStore()
assert complete(Task("write docs"), store).status is Status.DONE and len(store.tasks) == 1
assert first_word(None) == "" and first_word("hello world") == "hello"
```

`from __future__ import annotations` at the top of every module. A `Protocol` lets tests pass a small fake instead of
mocking internals.
