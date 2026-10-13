---
name: debugging
description: Use when something fails and the cause is not obvious - a failing test, an error, wrong output, a flaky or slow behaviour - build a fast reproduction first, find the root cause, then fix it once and add a regression test
---

# Debugging: find the cause before you change anything

Use this when a failure is not explained by the error message itself, and always on the second failed attempt at the same problem.

## The feedback loop is the skill
Before you form a theory, get a **fast, deterministic command that shows the exact symptom** and answers pass or fail: a failing test, a
small script, a recorded input replayed, a minimal harness. Make it fast (seconds), narrow (only the symptom) and repeatable (for a flaky
bug run it many times, or fix the seed, clock and order, until it fails reliably). Without such a loop you are guessing; spend your effort
building it. Only if that is impossible, ask the user to run a script for you and paste the result.

## The steps
1. **Read the whole error** (message, stack, the line it points at) and the code around it. Check what changed recently.
2. **Reproduce** with the loop above. Shrink the input until removing anything makes the bug go away.
3. **Trace backwards** from the wrong value to where it first became wrong. Look at the data at each boundary (add a print or log at the
   edges), not only where it crashes.
4. **Compare** with working code that does something similar; list every difference.
5. **One hypothesis**: write "I think X causes Y because Z". Test it with the smallest change that could prove it wrong. If it is wrong,
   form a new one; do not stack fixes.
6. **Fix the cause**, once, without cleaning up other things in the same change. Write a test that failed before the fix and passes after.
7. **Verify**: the loop passes, the whole test suite passes, the original symptom is gone. Remove your debugging output.

## When it does not work
- After **three failed fixes** stop patching. Several fixes failing, or each one revealing a new problem, usually means the design is
  wrong: say what you now believe about the design and change that, or tell the user.
- Do not "try one more thing" without a hypothesis. Do not change several things at once. Do not raise a timeout to hide a race: wait for
  the condition instead.
- A bug in a library you call is rare. Check your use of it (installed version, the documentation for that version) first.

## Performance bugs
Measure first (time the operation, profile with `python -m cProfile -s cumtime`), change one thing, measure again. Report the numbers
before and after.

## Gotchas
- "It works on my input" means the loop does not reproduce the failing case; get the real failing input.
- Printing the value you expect, not the value you have, hides the bug: print the actual variable.
