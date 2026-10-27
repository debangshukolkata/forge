---
id: rcp-stack-trace-fixing
type: recipe
title: Fixing a production error from a stack trace
summary: "Read bottom-up, find the first frame in our code, hypothesise, reproduce with a failing test, fix the cause, add a regression test."
moods: [methodical]
products: [bug fix, any python code, web]
tags: [traceback, stack trace, debugging, regression test, production]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-27)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Fixing a production error from a stack trace

A traceback lists calls from the outermost to the innermost; the error is at the bottom. Work from the bottom up.

Procedure:
1. **Read the last line first**: exception type and message. `KeyError: 'email'` and `TypeError: 'NoneType' object is not subscriptable` already narrow it down.
2. **Go up the frames until the first one in our own code.** Frames inside libraries are usually the symptom; the first frame
   in our code is usually where the bad value came from or was used wrongly.
3. **Look at the line and its inputs.** What values could each name hold? Which one was not what the code assumed
   (None, empty, wrong type, missing key, huge, non-ASCII)? Use the logs and the request that failed to learn the real input.
4. **State a hypothesis in one sentence**: "`load_user` returns None for deleted users and `render` does not check."
5. **Reproduce with a failing test** that feeds that input to the smallest function involved. If you cannot make it fail, your
   hypothesis is wrong or you lack a fact; get the fact, do not guess a fix.
6. **Fix the cause, not the symptom.** A bare `try/except` around the failing line hides the bug; ask why the bad value exists
   and fix it there, or decide explicitly what the code should do with it (reject, default, show a message).
7. **Check the neighbours**: other callers or branches with the same assumption.
8. **Keep the regression test**, run the suite, and write down in the commit: what failed, why, how it was fixed.
9. If the trace came from an exception raised while handling another ("During handling of the above exception"), the *first* exception is usually the real one.

```python
# runnable
import traceback


def load_user(user_id):
    return {1: {"name": "Asha"}}.get(user_id)  # returns None for unknown users


def greeting(user_id):
    user = load_user(user_id)
    return "Hello " + user["name"]  # the bug: user can be None


try:
    greeting(2)
except Exception as error:
    text = "".join(traceback.format_exception(error))
    frames = traceback.extract_tb(error.__traceback__)

print(text.strip().splitlines()[-1])
assert text.strip().splitlines()[-1].startswith("TypeError")
names = [frame.name for frame in frames]
print(names)
assert names[-1] == "greeting"  # innermost frame in our code: the line that used the bad value
assert frames[-1].line.startswith('return "Hello " + user["name"]')


# fixed: decide what unknown users mean, here an explicit error the caller can handle
class UnknownUser(LookupError):
    pass


def greeting_fixed(user_id):
    user = load_user(user_id)
    if user is None:
        raise UnknownUser(user_id)
    return "Hello " + user["name"]


# regression tests
try:
    greeting_fixed(2)
except UnknownUser:
    pass
else:
    raise AssertionError("expected UnknownUser")
assert greeting_fixed(1) == "Hello Asha"
```

Gotchas:
- The bottom line shows where it *blew up*, not always where it *went wrong*; the bad value may have been made several frames earlier.
- Log the exception with `logger.exception(...)` so the full trace survives; a message alone is not enough.
- Do not catch `Exception` and continue just to stop the alert.
- Traces from async code or threads may lack the caller; add context (ids, inputs) to the log.
- Line numbers in the trace refer to the deployed version; check out that commit before reading the code.
- Never paste a trace with tokens, emails or personal data into tickets or chats without removing them.
