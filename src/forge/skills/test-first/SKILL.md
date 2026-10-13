---
name: test-first
description: Use when you build a new function, module or feature, or fix a bug, and the work is more than a few lines - write the spec and a failing test first, then implement in small verified steps
---

# Test first, in small verified steps

Use this for any code task with real logic: a new function or module, a feature, a bug fix. Skip it for a typo, a rename or a
configuration value. Deciding and moving on is part of the method: write your spec down and keep going, do not stop to ask for approval.

## 1. Spec before code
Write the behaviour in a few lines before any code: inputs, outputs, edge cases, error cases (what is raised or returned, with which
message), and anything the user said exactly (names, formats, limits). Put it where the tests can quote it (the module docstring or
`docs/<feature>.md`). If the request is vague, decide the open points yourself, write the decision in the spec and mention it in your
summary.

## 2. One behaviour at a time (vertical slices)
Do not write all the tests and then all the code. Take the most important behaviour, write one test for it, run it and watch it fail for
the right reason (the feature is missing, not a typo or an import error), write the simplest code that passes, run the tests, then take
the next behaviour. Each new test is chosen from what the last step taught you. Refactor only while the tests are green.

New functions and every bug fix get a failing test first. A bug fix starts with a test that reproduces the bug; if it passes at once, it
is not testing the bug.

## 3. Tests that prove something
- Test behaviour through the public interface (what a caller sees), not private helpers or mocks of your own internals; the tests should
  still pass after a refactor.
- Take expected values from an independent source: the spec, a worked example, a known result. Do not compute them with the same logic as
  the code (that only proves the code equals itself).
- Cover the edges the spec names: empty input, the boundary value, the value just past it, duplicates, the error path, ordering and ties.
  A test with no assertion, or `assert True`, proves nothing.
- Use `pytest.mark.parametrize` for many similar cases; the case that fails should say which one it was.

## Do my tests really test it? (`mutation_check`)
For a module with real edges (limits, comparisons, calculations) run `mutation_check` on it: it makes a few deliberate mistakes one at a
time and tells you which ones your tests did not notice. Each survivor that matters needs a test that would have failed. The quality
gate also warns about tests that cannot fail (no assertion, `assert True`, a test that only checks its mocks).

## 4. Never weaken a test to get green
If a test fails, the code or your understanding is wrong. Change the test only when the spec itself changed, and say so. Do not delete a
failing test, loosen an assertion, or add a skip.

## 5. Finish
Run the project's whole test command (not only your new file), fix what you broke, and name every failure you see, also ones you did
not cause. A task is done when the full run passes, or you say exactly what still fails and why.

## Gotchas
- Time, randomness, the network and the file system make tests flaky: inject a clock, seed the generator, use `tmp_path`, never sleep
  for a fixed time.
- A test that only mirrors the implementation (same loop, same formula) passes even when the code is wrong.
