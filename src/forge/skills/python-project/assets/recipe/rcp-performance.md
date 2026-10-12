---
id: rcp-performance
type: recipe
title: "Make it fast, with evidence"
summary: "Measure first, pick the right data structure, generators, caching, and the usual O(n squared) traps."
moods: [robust]
products: [performance, data, any python code]
tags: [performance, profiling, complexity, cache]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-13)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Make it fast, with evidence

Rules: measure before changing (`python -m cProfile -s cumtime script.py`, `timeit`); fix the biggest cost, not the
guess; the usual wins are algorithmic: a `set` or `dict` for membership instead of scanning a list, one pass instead of
nested loops, sort once, avoid repeated string concatenation in loops (use `"".join`), read big files lazily line by line,
use generators for pipelines, cache pure functions with `functools.lru_cache`, batch database or network calls instead of
one per item. Keep the slow version's output as the test oracle.

```python
# runnable
import random
import time
from collections import Counter
from functools import lru_cache


def duplicates_slow(items: list[int]) -> list[int]:
    result: list[int] = []
    for i, x in enumerate(items):
        if x not in result and x in items[i + 1 :]:  # scans the list for every item: O(n squared)
            result.append(x)
    return result


def duplicates_fast(items: list[int]) -> list[int]:
    counts = Counter(items)
    seen: set[int] = set()
    result = []
    for x in items:
        if counts[x] > 1 and x not in seen:
            seen.add(x)
            result.append(x)
    return result


@lru_cache(maxsize=None)
def fib(n: int) -> int:
    return n if n < 2 else fib(n - 1) + fib(n - 2)


rng = random.Random(3)
sample = [rng.randint(0, 50) for _ in range(300)]
assert sorted(set(duplicates_slow(sample))) == sorted(duplicates_fast(sample))  # same answer: the old version is the oracle
big = [rng.randint(0, 10**6) for _ in range(300_000)]
start = time.perf_counter()
duplicates_fast(big)
assert time.perf_counter() - start < 2.0
assert fib(80) == 23416728348467685
```

Pandas/NumPy: operate on whole columns (vectorised), never loop over rows with `iterrows`; read only the columns you need
(`usecols`), give columns narrow dtypes. When it is still too slow after the algorithm is right: processes for CPU work,
asyncio or threads for waiting, then a compiled helper.
