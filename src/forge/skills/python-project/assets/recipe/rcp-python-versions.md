---
id: rcp-python-versions
type: recipe
title: Modern Python idioms (3.11 to 3.14)
summary: "What to use, and which Python version each feature needs, so code runs on the target."
moods: [clean]
products: [any python code]
tags: [python 3.11, python 3.12, python 3.13, python 3.14, idioms]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-13)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Modern Python idioms (3.11 to 3.14)

The project baseline is Python 3.11 (tests run on 3.13 and 3.14). Use these without a version check; the later ones only
when `requires-python` allows.

3.11: `tomllib` (read TOML), `StrEnum`, `asyncio.TaskGroup` and `asyncio.timeout`, `ExceptionGroup` with `except*`,
`typing.Self`, `X | None` everywhere, `match` statements (3.10).
3.12: `type Alias = list[int]` and `def first[T](items: list[T]) -> T` (PEP 695), `@typing.override`,
`itertools.batched`, `pathlib.Path.walk`, f-strings can nest quotes.
3.13: `warnings.deprecated`, `copy.replace`, better REPL, optional free-threaded build (do not rely on it).
3.14: annotations are evaluated lazily (PEP 649), template strings `t"..."` (PEP 750), `annotationlib`.

```python
# runnable
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

config = tomllib.loads('[tool]\nname = "demo"\nlevels = [1, 2, 3]')
assert config["tool"]["levels"] == [1, 2, 3]


@dataclass(slots=True, kw_only=True)
class Job:
    name: str
    tags: list[str] = field(default_factory=list)  # a mutable default must come from default_factory


def describe(value: int | str | list[int]) -> str:
    match value:
        case int(n) if n < 0:
            return "negative"
        case int():
            return "number"
        case str() as text:
            return f"text of {len(text)}"
        case [first, *rest]:
            return f"list starting {first} with {len(rest)} more"
        case _:
            return "empty list"


assert Job(name="x").tags == []
assert [describe(v) for v in (-1, 5, "abc", [1, 2, 3], [])] == [
    "negative", "number", "text of 3", "list starting 1 with 2 more", "empty list",
]
assert Path("a") / "b" == Path("a/b")
```

Always: `pathlib` instead of string paths, `with open(..., encoding="utf-8")`, f-strings, `enumerate`/`zip(strict=True)`
instead of index loops, `dict.get`/`setdefault`/`collections.defaultdict`, comprehensions for simple loops, `is None` checks.
