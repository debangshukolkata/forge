---
id: rcp-async
type: recipe
title: Async patterns that do not hang
summary: "gather, semaphores, timeouts, TaskGroup and clean cancellation with asyncio."
moods: [robust]
products: [async, io, workers, api clients]
tags: [asyncio, concurrency, timeout]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-13)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Async patterns that do not hang

Rules: async is for waiting on I/O, not for CPU work (use a process pool for that); never call blocking functions
(`time.sleep`, `requests.get`, file reads of big files) inside `async def` (use `asyncio.sleep`, an async client or
`asyncio.to_thread`); limit concurrency with a semaphore; put a timeout on every network wait; let `CancelledError`
propagate; use `asyncio.run(main())` once at the entry point.

```python
# runnable
import asyncio


async def fetch(number: int, gate: asyncio.Semaphore, active: list[int], peak: list[int]) -> int:
    async with gate:  # at most 3 at a time
        active[0] += 1
        peak[0] = max(peak[0], active[0])
        await asyncio.sleep(0.01)
        active[0] -= 1
        return number * 2


async def main() -> list[int]:
    gate, active, peak = asyncio.Semaphore(3), [0], [0]
    async with asyncio.TaskGroup() as group:  # Python 3.11+: if one task fails the others are cancelled
        tasks = [group.create_task(fetch(n, gate, active, peak)) for n in range(10)]
    assert peak[0] == 3
    return [task.result() for task in tasks]


async def slow() -> None:
    await asyncio.sleep(5)


async def with_timeout() -> bool:
    try:
        async with asyncio.timeout(0.05):  # Python 3.11+
            await slow()
    except TimeoutError:
        return True
    return False


assert asyncio.run(main()) == [n * 2 for n in range(10)]
assert asyncio.run(with_timeout()) is True
```

`asyncio.gather(*coros, return_exceptions=True)` when you want every result even if some fail. Tests: call the coroutine
with `asyncio.run(...)`; no plugin is needed for simple cases.
