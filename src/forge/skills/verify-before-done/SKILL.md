---
name: verify-before-done
description: Use before you say work is done, fixed or passing, before task_update(done), a commit or a final summary, and when the user asks “is it fixed?”, “wrap it up” or “mark it complete”: run the command that proves the claim now, read its whole output, report what it showed. Not for UI walkthroughs (web-ui-verification).
---

# Evidence before claims
(Adapted from obra/superpowers verification-before-completion, MIT.)

A claim of success needs a command you ran **after your last edit**, whose output you read. Memory of an earlier run, "it should
work" and "the change is small" are not evidence.

## Before you write "done", "fixed", "passes" or "works"
1. **Name the command that would prove it** (the test command, the linter, the build, the request that used to fail).
2. **Run it in full for a final claim** (narrower checks are for the steps before it, see below), and read the whole output: the exit code, the count of failures, warnings that matter.
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

## Know what a check is for, and stop when it has answered
The full run above is for the **final claim**. Every check before it has a narrower purpose: say it in one line first
("does the 404 case pass?", "does the module import?", "did the fix remove this failure?"), then use the smallest command that
answers it and stop when it has.
- **One behaviour:** run that test (`pytest path::test_name -q`), not the file or the suite.
- **Find out what is broken:** `pytest -x -q` (stop at the first failure), or `--lf` (the tests that failed last time) after a fix.
- **A slow or long run:** read the first failure and stop the run; do not wait for the other 200 tests to say the same thing.
- **A server, page or script check:** one request or one screenshot that shows the thing, not a full walkthrough.
- **A command that has run longer than expected with nothing new:** stop it, narrow the scope, and run that.
- Say in the note what you ran **and what you did not run**. A narrowed run never supports "all tests pass".
- The full suite (or the whole build) runs once, after the last edit, before "done". An early stop is for the steps in between.

## Rules of thumb
- Words like "should", "probably" and "seems to" mean you have not checked: check, or say it is unchecked.
- A change made after the last run restarts the clock: run again. A repeated run with no change in between adds nothing.
- Say what you could not check (needs the user's database, a server, a browser you cannot open) in the summary, plainly. An
  unchecked part is reported as unchecked, never as done.
- Do not cheer before the output is read. State the result and the evidence.

## Gotchas
- (2026-10-29, t22_security_fix) A security review is not done when the existing tests pass: list every function that takes outside input, name the sinks it reaches (HTML, link, redirect, file, SQL, shell, deserialiser, evaluator) and write one hostile test per pair; the recipe rcp-security has the checks. In t22 one rewrite passed its 12 tests and missed javascript: links, open redirects and a signed non-dictionary cookie.
- (2026-10-29, TI3 2026-10-29, D-559) When an existing test fails after your change, decide whether its old expectation is still right before you edit it. A changed expected value needs a reason from the requirement; check what the old value protected (uniqueness, ordering, an id sequence). In TI3 a count change made new claim numbers repeat an existing one, and the test was edited to expect the duplicate; the right fix was in the code that derived the number.
