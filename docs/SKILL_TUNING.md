# Skill description tuning (TODO C14)

Only each skill's one-line description is pinned for the model; whether a skill is loaded at the right moment depends on that line alone. This is the loop that measures
and improves it. The idea (should-trigger and should-not-trigger queries, a train/test split, keep the best description on the held-out set) comes from Anthropic's
skill-creator; the implementation is ours: `scripts/benchmark/run_skill_triggers.py` (CLI), `scripts/benchmark/skill_trigger_lib.py` (pure logic, tested in
`tests/test_skill_triggers.py`), queries in `tests/benchmarks/skills/triggers.json`.

## Method

- `triggers.json` holds, for 12 skills, 10 `should` queries (a realistic user message the skill is for, in varied wording, none naming the skill) and 10 `should_not`
  queries. The `should_not` ones are hard negatives: near-misses that belong to a sibling skill or to none.
- For each query the model gets the same skills index the agent has pinned (`parity.skills.index_text(discover())`, nothing re-implemented) and the question:
  "A user writes: ... Which ONE skill from the list, if any, would you load first? Answer with only the skill name or NONE."
- A `should` query is a hit when the model names that skill. A `should_not` query is a false trigger when the model names the skill under test (naming a sibling or NONE is correct).
  Accuracy = (hits + correct rejections) / all queries.
- Train/test split (per skill, per kind): the queries are ordered by the SHA-1 of `skill|kind|query` and the first 60% are train, the rest test (6 and 4 of 10). It is
  stable across runs and independent of the order in the file.

## Run

```
python scripts/benchmark/run_skill_triggers.py queries                          # counts and checks the file, no model call
python scripts/benchmark/run_skill_triggers.py eval                             # all 12 skills
python scripts/benchmark/run_skill_triggers.py eval --skills test-first,debugging --repeat 3 --model judge
python scripts/benchmark/run_skill_triggers.py tune web-ui-verification --candidates 4
python scripts/benchmark/run_skill_triggers.py tune web-ui-verification --apply  # only when you agree with the table
```

`eval` writes `results.json` and `results.md` to `C:\Work\ForgeRuns\skilltriggers\<time>\` (or `--out`): per skill the recall on `should`, the false-trigger rate on
`should_not`, and the confusions (which skill was chosen instead, or NONE). `--repeat N` asks each query N times and counts a trigger only when more than half of the answers agree.
`--model` names the router role that answers (default `judge`); use the role that matches the model the agent runs on, because under-triggering is model-specific.

`tune <skill>`: scores the current description on train and test, shows the train failures and false triggers to the model and asks for N rewrites (rules: start with
"Use when", a little pushy, say what it is not for, under 400 characters, no shouting; candidates that break the rules are dropped), scores every candidate on train and test
by swapping the description in memory (no file is touched), prints a table and recommends the candidate with the best test accuracy that does not lose on train, and only if it
beats the current description on test. With `--apply` the recommended description replaces the `description:` line of that skill's `SKILL.md` and a record (date, old and
new description, scores) is appended below.

## Reading a result

- 10 queries per kind is a small sample: one query is 10 points. Treat a one-query difference as noise; repeat with `--repeat 3` before trusting it, and prefer changes that fix a
  whole group of misses (for example every "fix this bug" message going to the wrong skill).
- A candidate that wins on train but not on test was fitted to the wording of the train queries; that is why only the test score chooses.
- Recall low with confusions pointing at one sibling: the two descriptions overlap; sharpen both. Recall low with NONE: the description does not name the situations; make it more explicit.
- This measures the choice of the skill from the index, not whether the skill then helps. That is `run_skill_ab.py` (D-417).

## Cost

Each query is one short call (index of about 22 lines plus one sentence). `eval` of all 12 skills is 240 calls (x N with `--repeat`). `tune` is 20 calls for the current
description, 20 per candidate and one for the rewrite, about 120 calls with 4 candidates. Calls run 4 at a time; a 429 is retried with growing waits.

## Nothing is applied automatically

`eval` never writes a skill. `tune` only prints a recommendation unless `--apply` is given. Review the new wording (and the diff) before committing it.

## Record of applied changes

(`tune --apply` appends below.)

- 2026-10-29 `test-first`: train recall 0/6, false triggers 0/6, accuracy 50% -> recall 5/6, false triggers 0/6, accuracy 92%; test recall 1/4, false triggers 0/4, accuracy 62% -> recall 3/4, false triggers 0/4, accuracy 88%.
  - old: Use when you build a new function, module or feature, or fix a bug, and the work is more than a few lines - write the spec and a failing test first, then implement in small verified steps
  - new: Use when a request says “add”, “implement”, “build” or “fix” code — like slugify, date-range merge, rate limiter, retry, parser — and you can write a spec and failing test before coding. Not for designing big abstractions (deep-modules) or fixing unknown failures (debugging).

- 2026-10-29 `verify-before-done`: train recall 3/6, false triggers 0/6, accuracy 75% -> recall 6/6, false triggers 0/6, accuracy 100%; test recall 2/4, false triggers 0/4, accuracy 75% -> recall 4/4, false triggers 0/4, accuracy 100%.
  - old: Use before you say work is done, fixed, passing or working, before task_update(done), a commit or a summary - run the command that proves the claim in this turn, read its whole output, and report what it showed
  - new: Use when the user says things like “we’re finished”, “is it fixed now?”, “mark this complete”, or asks for a summary or status yes/no, even for small tasks: actually run the check command and describe its output; not for UI walkthroughs (use web-ui-verification).

**2026-10-29, hand edit after the tuning above (D-535):** the applied `verify-before-done` candidate named only things the user says ("we're finished", "is it fixed?") and dropped the agent's own moment (before `task_update(done)`, a commit or a summary), which this eval cannot measure because it asks about user messages only. The description now names both; re-evaluated: 10/10 recall, 0/10 false triggers.
