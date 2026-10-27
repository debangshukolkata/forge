---
id: rcp-differential-review
type: recipe
title: Reviewing a diff (differential review)
summary: "Read the diff first, list behaviour changes, check callers and tests, then look hard at risky categories."
moods: [careful]
products: [code review, any python code]
tags: [code review, diff, pull request, callers, regression, risk]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-27)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Reviewing a diff (differential review)

A review looks at what *changed*, and at what the change can break elsewhere. Do not start by reading whole files.

Procedure:
1. **Read the description, then the whole diff once** without judging. Note the intent in one sentence. If the diff does more than that sentence, say so.
2. **List the behaviour changes** as plain statements: "empty input now returns [] instead of raising", "timeout 30 s to 5 s".
   Renames, moves and formatting are not behaviour changes; separate them out.
3. **For each changed function or signature, find its callers** (search for the name). Does every caller still pass valid
   arguments and handle the new return value, new exception or new `None`?
4. **Check the tests**: is there a test that fails without this change? Do the changed lines have a test for both the normal and the edge case? Were tests deleted or loosened?
5. **Walk the risky categories** and ask if the diff touches them: authentication and permissions, input from outside, SQL and
   shell, file paths, money and rounding, time zones, concurrency and shared state, error handling that swallows, migrations
   and data formats, config and defaults, new dependencies.
6. **Read the edges of each hunk**: the lines just above and below the change often hold the condition or variable it depends on.
7. **Run it** if you can: tests, then the one scenario the change is about.
8. **Write findings by severity**: must fix (bug, security, data loss), should fix, nit. Say *why* and suggest the fix. Praise what is good and clear.

```python
# runnable
import ast
import difflib

OLD = """
def total(prices):
    return sum(prices)

def label(name):
    return name.strip()

def discount(price):
    return price * 0.9
"""

NEW = """
def total(prices, tax=0.0):
    return sum(prices) * (1 + tax)

def label(name):
    return name.strip()

def apply_discount(price):
    return price * 0.8
"""


def function_sources(source):
    tree = ast.parse(source)
    return {
        node.name: ast.get_source_segment(source, node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def summarise(old, new):
    before, after = function_sources(old), function_sources(new)
    report = {
        "added": sorted(set(after) - set(before)),
        "removed": sorted(set(before) - set(after)),
        "changed": [],
    }
    for name in sorted(set(before) & set(after)):
        if before[name] != after[name]:
            report["changed"].append(name)
    return report


report = summarise(OLD, NEW)
print(report)
assert report == {"added": ["apply_discount"], "removed": ["discount"], "changed": ["total"]}
# 'removed' + 'added' may be a rename: check by similarity, then search for callers of the old name
ratio = difflib.SequenceMatcher(
    None, function_sources(OLD)["discount"], function_sources(NEW)["apply_discount"]
).ratio()
assert ratio > 0.5  # looks like a rename that also changed 0.9 to 0.8: a behaviour change hiding in a rename
diff = list(difflib.unified_diff(OLD.splitlines(), NEW.splitlines(), lineterm=""))
assert any(line.startswith("-    return price * 0.9") for line in diff)
```

Gotchas:
- A rename plus a value change is the classic hiding place (the example): compare bodies, not only names.
- Adding a parameter with a default is safe for callers but not for subclasses or code that passes positional arguments.
- "Tests pass" only matters if a test exercises the changed line; check coverage of the hunk, not the whole suite.
- Generated files, lock files and snapshots: skim for size and surprises, review the source that produced them.
- Large diffs hide bugs. Ask for a split rather than reviewing tired.
- Review the diff you are shown, then ask what is *missing*: the missing test, the missing caller update, the missing migration.
