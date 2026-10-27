---
id: rcp-debug-ci-failure
type: recipe
title: Debugging a failing CI run
summary: "Reproduce locally with the same versions and commands, read the first failure, separate flaky from deterministic, compare environments, bisect."
moods: [methodical]
products: [ci, any python code]
tags: [ci, pytest, flaky tests, debugging, bisect, environment]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-27)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Debugging a failing CI run

CI says red and you cannot see the machine. The job is to turn "fails over there" into "fails here, in one command".

Procedure:
1. **Find the first failure, not the last.** Scroll to the first error line in the log. Later errors are often fallout (a fixture
   broke, so fifty tests errored). The short summary at the end of a pytest run lists failures; start with the earliest.
2. **Write down the facts**: which job and step, exact command, Python and OS version, dependency versions (the log usually prints them), the commit.
3. **Reproduce with the same command and versions.** Same Python minor version, same install step (lock file, not "latest"),
   same environment variables, same working directory. Run only the failing test: `pytest path::test_name -x`.
4. **Deterministic or flaky?** Run the failing test 10-20 times (`pytest --count` if available, or a shell loop). Fails every
   time: a real bug or environment gap. Fails sometimes: look for time, ordering, randomness, shared files or ports, network, threads.
5. **If it only fails in the full run**, test order is leaking state. Run the failing test alone, then with the files before it; shrink until two tests remain.
6. **If it fails only in CI**, compare environments: Python version, OS (paths, line endings, case sensitivity), time zone and
   locale, missing system package, missing env var or secret, no network, clean cache, a newer dependency released overnight.
7. **If you cannot tell what changed**, bisect: `git bisect run <command>` between the last green commit and the first red one.
   For dependencies, bisect the versions (pin the one that changed).
8. **Fix the cause**, add or tighten a test so it fails the same way locally, and push. Do not just re-run until green, and do not add retries to hide a flaky test without a ticket.

```python
# runnable
import re

LOG = """
============ short test summary info ============
FAILED tests/test_cart.py::test_total_with_tax - AssertionError: assert 10.5 == 10.0
FAILED tests/test_cart.py::test_empty_cart - KeyError: 'items'
ERROR tests/test_db.py::test_insert - sqlite3.OperationalError: no such table: users
========= 2 failed, 1 error, 41 passed in 3.20s =========
"""

PATTERN = re.compile(r"^(FAILED|ERROR) (?P<file>[^:\s]+)::(?P<test>\S+)(?: - (?P<reason>.*))?$", re.MULTILINE)


def parse_failures(text):
    return [
        {"kind": m.group(1), "file": m["file"], "test": m["test"], "reason": m["reason"] or ""}
        for m in PATTERN.finditer(text)
    ]


failures = parse_failures(LOG)
assert len(failures) == 3
assert failures[0]["test"] == "test_total_with_tax"
assert (
    failures[2]["kind"] == "ERROR"
)  # an error in setup, not an assertion: look at fixtures and environment first
by_file = {}
for failure in failures:
    by_file.setdefault(failure["file"], []).append(failure["test"])
print(by_file)
assert by_file["tests/test_cart.py"] == ["test_total_with_tax", "test_empty_cart"]
```

Gotchas:
- `ERROR` (setup or collection) and `FAILED` (assertion) are different problems; errors often point at the environment.
- Timeouts and "killed" mean memory or a hang, not a wrong answer; look at the step before the kill.
- Tests that pass locally because of a leftover file, database or cached `.pyc` fail on a clean runner; run in a fresh clone or temp dir.
- Dates and time zones: CI runs in UTC; a test that depends on "today" or local midnight is flaky by design.
- Do not trust "it passed on re-run"; record the flaky test and find the shared state.
- Never print secrets while debugging CI; a log line stays forever.
