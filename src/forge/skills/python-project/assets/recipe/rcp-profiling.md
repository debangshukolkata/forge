---
id: rcp-profiling
type: recipe
title: Profiling slow Python code
summary: "Measure first: timeit for small snippets, cProfile for where time goes, tracemalloc for memory; read the profile, then change one thing."
moods: [fast]
products: [any python code, web, cli, data]
tags: [profiling, cprofile, timeit, tracemalloc, performance, benchmark]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-27)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Profiling slow Python code

Never optimise from a hunch. Programs spend their time in a few places and they are rarely the ones you guess.

Procedure:
1. **Say what "slow" means**: a number and a input size ("report for 50k rows takes 9 s, target 2 s"). Without it you cannot know when to stop.
2. **Make it repeatable**: a script or test that runs the slow path with fixed input, no network, no random data.
3. **Time the whole thing** with `time.perf_counter()` or `timeit` (several repeats, take the minimum).
4. **Profile with cProfile**: `python -m cProfile -o out.prof script.py`, then read it with `pstats` sorted by `cumulative`
   (who is responsible) and by `tottime` (who burns the time itself).
5. **Read the profile top-down**: find the first of your own functions with a large cumulative time, then look at what it calls.
   A function called a million times with a tiny cost each is a loop to remove; one call with a huge cost is the algorithm.
6. **Reason at line level** inside that one function: a loop inside a loop, a list searched with `in`, a string built with `+=`,
   a query or file read inside a loop, a regex compiled on every call. (A line profiler is optional; `perf_counter` around
   suspect lines does the job.)
7. **Memory**: `tracemalloc.start()`, run, `take_snapshot().statistics("lineno")` shows which lines hold the most memory.
8. **Change one thing, measure again** with the same input. Keep the change only if the number moved and the tests still pass.
9. Stop at the target. Write the before/after numbers in the commit message.

```python
# runnable
import cProfile
import io
import pstats
import timeit
import tracemalloc


def slow_unique(items):
    result = []
    for item in items:
        if item not in result:  # linear search inside a loop: quadratic overall
            result.append(item)
    return result


def fast_unique(items):
    return list(dict.fromkeys(items))  # keeps order, constant-time membership


data = [n % 700 for n in range(6000)]
assert slow_unique(data) == fast_unique(data)

profiler = cProfile.Profile()
profiler.enable()
slow_unique(data)
profiler.disable()

buffer = io.StringIO()
stats = pstats.Stats(profiler, stream=buffer).sort_stats("tottime")
stats.print_stats(3)
top_function = stats.sort_stats("tottime").fcn_list[0]  # (file, line, name)
print("top entry:", top_function[2])
assert top_function[2] == "slow_unique"

slow_time = min(timeit.repeat(lambda: slow_unique(data), number=3, repeat=3))
fast_time = min(timeit.repeat(lambda: fast_unique(data), number=3, repeat=3))
print(f"slow {slow_time:.4f}s  fast {fast_time:.4f}s")
assert fast_time < slow_time

tracemalloc.start()
fast_unique(data)
current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
assert peak > 0
```

Gotchas:
- Profiling adds overhead; use it to find *where*, use `timeit` for *how much*.
- Run the profile on realistic input size; a small input hides quadratic behaviour.
- The first run is warmer or colder than the rest (caches, imports); repeat and take the minimum.
- Time spent waiting (network, disk, locks) shows up as one slow call, not many; the fix is fewer calls, batching or caching, not faster Python.
- Do not profile with the debugger or a coverage tool on; both distort the numbers.
- A speed-up that changes results is a bug; keep a test that compares old and new output, as the example does.
