---
name: verify-before-done
description: Use before you say work is done, fixed, passing or working, before task_update(done), a commit or a summary - run the command that proves the claim in this turn, read its whole output, and report what it showed
---

# Evidence before claims
(Adapted from obra/superpowers verification-before-completion, MIT.)

A claim of success needs a command you ran **after your last edit**, whose output you read. Memory of an earlier run, "it should
work" and "the change is small" are not evidence.

## Before you write "done", "fixed", "passes" or "works"
1. **Name the command that would prove it** (the test command, the linter, the build, the request that used to fail).
2. **Run it in full**, not a part of it, and read the whole output: the exit code, the count of failures, warnings that matter.
3. **Compare** the output with the claim. If it does not confirm it, say what it does show, with the numbers.
4. Only then make the claim, and put the evidence next to it ("`pytest`: 212 passed, 0 failed").

## What counts as proof
| Claim | Needs | Does not prove it |
|---|---|---|
| Tests pass | the test command's output: 0 failures | an earlier run, "should pass" |
| Lint or types clean | that tool's output: 0 errors | a different tool passing |
| It builds | the build command, exit 0 | lint passing, "logs look fine" |
| The bug is fixed | the original symptom no longer happens (the failing case itself) | the code changed, so it must be fixed |
| The new test is a real regression test | it **fails** with the fix removed and passes with it | it passes once |
| Requirements are met | each requirement checked one by one against the running result | the tests pass |
| A subagent or builder succeeded | its changed files read and its checks re-run by you | its report says success |

## Rules of thumb
- Words like "should", "probably" and "seems to" mean you have not checked: check, or say it is unchecked.
- A change made after the last run restarts the clock: run again. A repeated run with no change in between adds nothing.
- Say what you could not check (needs the user's database, a server, a browser you cannot open) in the summary, plainly. An
  unchecked part is reported as unchecked, never as done.
- Do not cheer before the output is read. State the result and the evidence.
