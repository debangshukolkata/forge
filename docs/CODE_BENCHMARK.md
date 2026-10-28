# Coding benchmark (TODO C1)

Measures how good the code DebCraft writes is, on the real model, so every change in TODO section 5b can be judged by numbers.
Status 2026-10-13: ten tasks and the runner are built and validated offline; the first full baseline is below. Written 2026-10-27, run for the first time 2026-10-28 (results at the end of this file; the judge scored them but does not discriminate): tasks t15 to t22 and the judge `scripts/benchmark/judge_code.py` (testing is scheduled after development; their references were only checked against their hidden tests in a scratch copy).

## Tasks (`tests/benchmarks/tasks/<id>/`)
| Id | Tier | What it asks for |
|---|---|---|
| t01_slugify | single function | `slugify` with accents, hyphen rules, word-boundary `max_length`, errors |
| t02_durations | single function | `parse_duration` / `format_duration`, strict validation, round trip |
| t03_ttl_cache | small module | TTL + LRU cache with an injected clock |
| t04_paginate_bug | bug fix in an existing repo | three bugs in `paginate()`, one visible failing test |
| t05_inventory_feature | feature in an existing repo | `low_stock_report` and `to_csv` added to a class |
| t06_billing_refactor | refactor, tests kept green | three duplicated functions into one `calculate_total`, thin wrappers |
| t07_wordstat_cli | CLI tool | argparse tool, stdin or file, text and JSON output, exit codes |
| t08_dedupe_perf | performance fix | two O(n^2) functions must handle 300,000 items |
| t09_async_jobs | async worker | bounded concurrency, retries with growing delay, ordered results, cancellation |
| t10_sales_pipeline | data pipeline | CSV report with validation, skipped-row log, per-region and per-month totals |
| t11_rate_limiter | precise spec, concurrency | token bucket and sliding window with an injected clock, exact boundaries, thread safety, no key leaks |
| t12_expr_calc | parser with error positions | expression evaluator without eval: precedence, right-associative power, unary minus rules, exact error positions |
| t13_todo_undo | multi-file feature, persisted format | undo/redo in an existing store + CLI, history in the JSON file, old files still load, history limit |
| t14_cron_next | calendar logic, many edge cases | next fire time of a cron expression: ranges, steps, names, the day-of-month/day-of-week rule, leap years, never-firing expressions |
| t15_rest_inventory_api | REST API on the standard library | WSGI app (`create_app()`): CRUD, validation with per-field details, 404/405/409/415, JSON errors, pagination and filter; tests call the app directly |
| t16_mode_a_repo_feature | feature across several modules of an existing repo | reservations/waiting list in a 10-file library-desk repo (loans, reports, CLI); existing tests stay green; `"mode": "A"` in task.json |
| t17_mode_b_no_host_code | new tool from a prose spec, no seed | log anonymiser with exact pseudonym hashing, secret/user/email/IPv4 rules, idempotence, report counts; `"mode": "B"` |
| t18_large_multifile_feature | large multi-file feature, persisted format | recurring subscriptions with proration (half-up rounding) across models, storage (JSON key added, `next_id` unchanged), new `billing.py`, report and CLI |
| t19_bug_hunt_concurrency | bug hunt: ordering, lease, thread safety | job queue with FIFO tie-break, stale-lease completion, reaping finished jobs, one attempt too many, peek/pop race; deterministic (injected clock) plus one threaded stress test |
| t20_migration_script | idempotent data migration | JSON schema v1 to v2: record rules, skip and log bad records, atomic write, backup never overwritten, second run changes nothing |
| t21_text_diff_patch | format parser, exact failure semantics | unified-diff parser and `apply_patch`: exact positions, no fuzz, conflict details, `\ No newline`, CRLF, reverse |
| t22_security_fix | security review and fix | brief-free "review and fix": SQL injection, path traversal, pickle sessions, `eval`, XSS, open redirect; hidden tests probe each |

Each task folder holds `task.md` (the prompt DebCraft gets), `task.json` (id, tier, entry module), `seed/` (files the "user" already
has, put in the workspace's `project/` folder), `hidden/` (tests DebCraft never sees) and `reference/` (a solution that proves the task
is solvable). `tests/test_benchmark_fixtures.py` checks, in the normal suite and without any model, that the reference passes every
hidden test and the seed's own tests, and that the hidden tests fail without the reference.

## Not covered yet
t15 to t22 now cover a framework-free REST service, a Mode A repository, a Mode B task with no host code, a large multi-file feature, a
concurrency bug hunt, a migration, a format parser and a security review. Still missing: a service that needs an installed framework,
UI or database work, and ambiguous requirements where the right move is to ask. Aim: 20 to 30 tasks (22 now).

Mode note: `run_code_benchmark.py` always creates a standalone (Mode B style) workspace and copies `seed/` into its `project/`
folder, so a task with a seed is "the user's pasted code" and a task without one has no host code. The `"mode"` key in
task.json (t16 `A`, t17 `B`) records the intent and is not read by the runner; a true Mode A run (repo copy opened by the agent)
is not implemented.

## Running it
```
.venv\Scripts\python scripts\benchmark\run_code_benchmark.py baseline-2026-10-14
.venv\Scripts\python scripts\benchmark\run_code_benchmark.py try-x --tasks t01_slugify,t04_paginate_bug --env SOME_SETTING=1
```
Work is under `C:\Work\ForgeRuns\codebench\<run-name>` (one workspace per task, an isolated DebCraft home, `results.json`,
`results.md`). The runner scores the delivered module with the hidden tests (the model's own test files are left out of scoring), and
records wall time, model calls, tool seconds, seconds waited for approvals, tokens and cost. Paste the table below with the date and
what changed.

## Judge rubric
Seven criteria, each scored 0 to 5 with a one-line reason, plus an overall score, a two-sentence summary and the worst problem:
correctness, edge cases, error handling, tests that prove something, security, simplicity, readability.

`scripts/benchmark/judge_code.py` does it automatically with the configured `judge` model role (Forge's own LLM client, as the
document and deck benchmarks do). It reads a run folder written by `run_code_benchmark.py`: for each task it builds a prompt from
`task.md`, the files delivered under `project/` and `output/` (changed or new files in full up to 14,000 characters each and 60,000
in total, unchanged seed files by name only) and the rubric, asks for one JSON object, validates the scores, and writes `judge.json`
and `judge.md` (a score table plus reasons) next to `results.json`. The judge cannot run the code and does not see the hidden tests
except for the pass count as context, so it is a second opinion, not a replacement for the hidden tests.
```
.venv\Scripts\python scripts\benchmark\judge_code.py baseline-2026-11-01
.venv\Scripts\python scripts\benchmark\judge_code.py try-x --tasks t15_rest_inventory_api,t22_security_fix --parallel 3 --model gpt54
```
Use a different model for judging than the one that wrote the code when you can (`--model`), and read a few judged tasks yourself
before trusting the scores: the first manual scores should show whether the judge agrees with you.

## Results
Smoke run 2026-10-13 (runner check, one task, current main at commit 1385806 plus runner fixes):

| Task | Tier | Hidden tests | Wall | Model calls | Tool s | Waited s | Tokens in/out | Cost |
|---|---|---|---|---|---|---|---|---|
| t01_slugify | single function | 17/17 | 146s | 12 | 10 | 0 | 238206/10093 | $0.192 |

Notes: 132 of the 146 seconds were model time; 12 calls read 238k input tokens for a 40-line module (the system prompt, skills and
tool schemas are re-sent each call), which is the number to watch under TODO S3/S4. The first scoring attempt failed only because the
workspace interpreter could not create temp files inside the tool sandbox; scoring now uses the repo's own interpreter.

### Run `baseline-2026-10-13` (2026-10-13 06:51)

| Task | Tier | Hidden tests | Wall | Model calls | Tool s | Waited s | Tokens in/out | Cost |
|---|---|---|---|---|---|---|---|---|
| t01_slugify | single function | 17/17 | 101s | 9 | 7 | 0 | 157666/9068 | $0.142 |
| t02_durations | single function | 32/32 | 82s | 6 | 10 | 0 | 111985/9306 | $0.137 |
| t03_ttl_cache | small module | 10/10 | 157s | 15 | 17 | 0 | 315408/12181 | $0.199 |
| t04_paginate_bug | bug fix in an existing repo | 11/11 | 122s | 13 | 21 | 0 | 218827/6682 | $0.121 |
| t05_inventory_feature | feature in an existing repo | 7/7 | 101s | 13 | 19 | 0 | 223121/5863 | $0.114 |
| t06_billing_refactor | refactor with tests kept green | 21/21 | 92s | 10 | 10 | 0 | 151567/4363 | $0.084 |
| t07_wordstat_cli | CLI tool | 11/11 (first scored 10/11, see note) | 158s | 13 | 17 | 0 | 277279/12407 | $0.196 |
| t08_dedupe_perf | performance fix | 4/4 | 96s | 10 | 10 | 0 | 158486/6378 | $0.105 |
| t09_async_jobs | async worker | 9/9 | 217s | 18 | 21 | 0 | 434946/18100 | $0.293 |
| t10_sales_pipeline | data pipeline | 13/13 | 178s | 19 | 19 | 0 | 424382/12762 | $0.227 |

Tasks fully passed: 10/10; hidden tests passed: 135/135 (after the t07 test fix below).

Notes on the baseline: total cost about $1.62 and about 21 minutes for 10 tasks; every task had 0 seconds waiting for approvals. The single failure in the first scoring (t07, one test) was a flaw in my hidden test, not in DebCraft's code: the test replaced stdin with a plain text stream, but the model correctly read bytes from `sys.stdin.buffer`. The test now uses a stream that has both, and the delivered code passes 11/11. Lesson for new tasks: tests must not fix how input is read. Consequence for the benchmark's usefulness: all ten tasks pass, so these tasks are too easy to tell changes apart; the next step is harder tasks (multi-file features, a Mode A repo, a REST service, ambiguous requirements) before tuning anything against it. Input tokens are 150k to 430k per task for 40 to 200 line outputs, so context size, not output, drives cost.

### Run `code-hard-1` (2026-10-13, the four harder tasks t11-t14)

| Task | Tier | Hidden tests | Wall | Model calls | Cost |
|---|---|---|---|---|---|
| t11_rate_limiter | precise spec, concurrency | 25/25 | 156s | 8 | $0.205 |
| t12_expr_calc | parser with error positions | 69/69 | 216s | 10 | $0.293 |
| t13_todo_undo | multi-file feature with a persisted format | 15/16 | 224s | 15 | $0.342 |
| t14_cron_next | calendar logic, many edge cases | 65/65 | 235s | 11 | $0.330 |

Fully passed 3/4; hidden tests 174/175; total $1.17. The one miss: t13 did not trim a history longer than 20 steps when it is read from a file (the limit was only applied when saving). A small spec corner, not a design flaw. Conclusion: even this harder tier is mostly solved, so the coding side is strong; the next separators are bigger multi-file tasks and ambiguous requirements, not more algorithm puzzles.

### Run `night-1` (2026-10-15 12:27)

| Task | Tier | Hidden tests | Wall | Model calls | Tool s | Waited s | Tokens in/out | Cost |
|---|---|---|---|---|---|---|---|---|
| t01_slugify | single function | 17/17 | 352s | 15 | 73 | 0 | 547546/14985 | $0.388 |
| t02_durations | single function | 32/32 | 154s | 7 | 7 | 0 | 208181/9451 | $0.186 |
| t03_ttl_cache | small module | 10/10 | 216s | 4 | 10 | 0 | 130265/13187 | $0.230 |
| t04_paginate_bug | bug fix in an existing repo | 11/11 | 240s | 9 | 63 | 0 | 266882/10451 | $0.184 |
| t05_inventory_feature | feature in an existing repo | 7/7 | 145s | 9 | 13 | 0 | 264848/8288 | $0.207 |
| t06_billing_refactor | refactor with tests kept green | 21/21 | 107s | 6 | 9 | 0 | 160323/4704 | $0.102 |
| t07_wordstat_cli | CLI tool | 11/11 | 171s | 4 | 10 | 0 | 124176/11574 | $0.171 |
| t08_dedupe_perf | performance fix | 4/4 | 119s | 5 | 10 | 0 | 132954/7279 | $0.129 |
| t09_async_jobs | async worker | 9/9 | 229s | 7 | 10 | 0 | 243755/13985 | $0.250 |
| t10_sales_pipeline | data pipeline | 13/13 | 499s | 14 | 165 | 0 | 570490/28772 | $0.532 |
| t11_rate_limiter | precise spec, concurrency | 25/25 | 246s | 7 | 9 | 0 | 255238/15191 | $0.288 |
| t12_expr_calc | parser with error positions | 69/69 | 418s | 7 | 14 | 0 | 265224/26758 | $0.394 |
| t13_todo_undo | multi-file feature with a persisted format | 15/16 | 331s | 7 | 16 | 0 | 265353/19583 | $0.322 |
| t14_cron_next | calendar logic, many edge cases | 65/65 | 433s | 8 | 12 | 0 | 367193/24678 | $0.352 |

Tasks fully passed: 13/14; hidden tests passed: 309/310.

Run on the final code of the night, three tasks at a time (`--parallel 3`, so the wall times are longer than the baseline's serial run: the model calls and the tokens are what compare). Total cost about $3.74 (the baseline's ten tasks cost $1.62; the four harder tasks $1.17 in code-hard-1). 13 of 14 tasks passed completely, 309 of 310 hidden tests; the one miss is the same corner as in code-hard-1: t13 does not trim a history longer than 20 steps when it reads it from a file. Nothing regressed against the 2026-10-13 runs.

### Run `night-gpt54` (2026-10-15 14:26)

| Task | Tier | Hidden tests | Wall | Model calls | Tool s | Waited s | Tokens in/out | Cost |
|---|---|---|---|---|---|---|---|---|
| t01_slugify | single function | 17/17 | 346s | 10 | 149 | 0 | 309823/10420 | $0.634 |
| t02_durations | single function | 32/32 | 380s | 15 | 164 | 0 | 474715/13055 | $0.731 |
| t03_ttl_cache | small module | 10/10 | 262s | 8 | 182 | 0 | 230493/7034 | $0.590 |
| t04_paginate_bug | bug fix in an existing repo | 11/11 | 121s | 5 | 48 | 0 | 131810/3601 | $0.328 |
| t05_inventory_feature | feature in an existing repo | 7/7 | 176s | 9 | 60 | 0 | 245416/5454 | $0.494 |
| t06_billing_refactor | refactor with tests kept green | 21/21 | 199s | 10 | 51 | 0 | 268048/5169 | $0.549 |
| t07_wordstat_cli | CLI tool | 11/11 | 512s | 14 | 213 | 0 | 521938/17834 | $0.995 |
| t08_dedupe_perf | performance fix | 4/4 | 325s | 10 | 208 | 0 | 278029/8818 | $0.651 |
| t09_async_jobs | async worker | 9/9 | 456s | 13 | 366 | 0 | 404864/11068 | $0.754 |
| t10_sales_pipeline | data pipeline | 13/13 | 359s | 10 | 136 | 0 | 300499/9903 | $0.603 |
| t11_rate_limiter | precise spec, concurrency | 25/25 | 427s | 16 | 127 | 0 | 564777/14202 | $1.170 |
| t12_expr_calc | parser with error positions | 69/69 | 754s | 15 | 272 | 0 | 695624/34899 | $1.503 |
| t13_todo_undo | multi-file feature with a persisted format | 15/16 | 275s | 9 | 128 | 0 | 280441/8679 | $0.741 |
| t14_cron_next | calendar logic, many edge cases | 65/65 | 504s | 14 | 209 | 0 | 474183/19785 | $0.921 |

Tasks fully passed: 13/14; hidden tests passed: 309/310.

Same fourteen tasks as `night-1`, three at a time, with gpt-5.4 as the coder, knowledge builder and summariser (`--coder-model gpt54`; reviewer, vision and judge unchanged). 13 of 14 tasks and 309 of 310 hidden tests, the same as gpt-5.1 and the same single miss (t13 does not trim a history read from a file). Against `night-1`: wall time about 5,100 s against 3,660 s (39 percent slower), 158 model calls against 109, cost $10.66 against $3.74 (2.9 times). On these tasks gpt-5.4 shows no correctness gain; they are easy (both models are near the ceiling), so this says nothing about much harder work.

## Approach challenges (TODO item 20, 2026-10-15)

Ten small tasks with one trap each (tests/benchmarks/challenges, run with `scripts/benchmark/run_challenges.py`, stopped at 5 minutes or 20 tool calls); only the approach is judged, from the
event log. Rounds: `night-1` (c01 to c08), `night-2` (c05, c08, c09, c10 after the first fixes), `night-3` (c08, c09, c10 after the second fixes).

| Challenge | First verdict | Fix | Verdict after the fix |
|---|---|---|---|
| c01 month boundary | right: reads the code path, failing test first, fix in `timeutil` | none | right |
| c02 loyalty discount | right: records the assumption, named constants | none | right |
| c03 event buckets | right: assumptions recorded, width validated, tests | none | right |
| c04 lost counts | right: reproduces with threads, names the race, lock | none | right |
| c05 product search | partly: parameterized, but did not tell the user about the injectable old function, LIKE wildcards not escaped | prompt rule: report what you notice, escape LIKE (D-408) | LIKE escaped; the notice is covered by the risk scan (D-410) |
| c06 CSV export | right: read `Result`, `format_money` and the fixtures first | none | right |
| c07 settings model | right: checked the installed pydantic with `library_api` first | none | right |
| c08 price refactor | wrong: rewrote the whole function in one step, no test run first | baseline gate (D-408), rewrite gate and refactor section in test-first (D-410) | better: runs the tests, probes the old numbers, is made to write a test before replacing the file; the pinning is still thin (one test edit) |
| c09 timeout helper (new) | wrong: never mentioned the pickle loader and the committed token | risk scan and one reminder before the turn ends (D-410) | right: the reply lists both as 'Noticed, not changed' |
| c10 shipping refactor (new) | wrong: rewrote the function before pinning anything | rewrite gate (D-410) | right: tests run first, a regression test written, then a small edit |

New gates for review (all are one reminder, never a trap, and only in real sessions): the first edit of existing source code is refused once until the tests have run or a test has been written
(`tools/baseline_gate.py`); a `write_file` that replaces most of an existing source file of 30 lines or more is refused once until a test has been written; before a turn ends the loop asks once for
the risks the scan found in the files it read (`safety/risk_scan.py`) if the reply does not name them; `design_candidates` refuses a composition that is not a catalogue id (D-406).
Limits: c08 shows that a gate asks for a test but cannot judge how complete the pinning is; one run per challenge is a hint, not a measurement.

### Run 2026-10-28: tasks t15 to t22 for the first time (current main at a00281c, real model, `--parallel 3`)
Run names: `c1-t15-t22-2026-10-28` (seven tasks) and `probe-t17` (t17 alone, 3 in parallel was not used for it). Tokens and cost are as the runner reports them.

| Task | Hidden tests | Wall | Model calls | Cost | Judge overall |
|---|---|---|---|---|---|
| t15_rest_inventory_api | 44/47 | 212s | 6 | $0.368 | 5 |
| t16_mode_a_repo_feature | 18/18 | 304s | 11 | $0.483 | 5 |
| t17_mode_b_no_host_code | 39/42 | 364s | 11 | $0.573 | not judged |
| t18_large_multifile_feature | 24/24 | 226s | 8 | $0.483 | 5 |
| t19_bug_hunt_concurrency | 17/19 | 362s | 11 | $0.528 | 5 |
| t20_migration_script | 80/86 | 232s | 8 | $0.319 | 5 |
| t21_text_diff_patch | 63/65 | 344s | 3 | $0.461 | 4 |
| t22_security_fix | 81/93 | 368s | 14 | $0.446 | 5 |

Fully passed: 2 of 8 tasks (t16, t18); hidden tests 366/394 (93 %). The failed tests per task (names in `results.json`, `tail`): t15 two 404 path cases and a bad-pagination case; t19 a stale worker completing a reassigned job and completion by a stranger or on a queued job; t20 six, including the log being appended not overwritten and the all-records-bad case; t21 a lone carriage return and a start beyond the text; t22 twelve, among them redirects containing a newline or a NUL.

**The judge does not discriminate.** It gave 5 of 5 to five tasks that failed hidden tests (mean 4.9). It sees the pass count only as context and reads the code without running it. Treat the hidden tests as the measure and the judge as a readability check; do not use its overall score to compare changes.
**Failures read against the task text (2026-10-28), t20, t21 and t22: the model is at fault, not the tests.** t22: `safe_redirect` still accepts `///evil.example`, `/\evil.example` and values with CR, LF or NUL (open redirect and header injection, the task says every argument is attacker-controlled), `calculate` now rejects a leading space (`" (2 + 3) * -4 "` raises, documented behaviour broken) and accepts `True`; the judge called these redirects "local-path-only" and gave 5. t20: the task says the log is appended; t21: it says a lone `
` is part of the line. **Read 2026-10-28 (failing tests only; the task text was searched, not read line by line):** t15 fails three checks (an invalid-UTF-8 body must give a JSON error, not crash; `/items/01` must be 404; a negative page must be 400; the task says page is an integer >= 1 and the 415/400 error rules are listed), t19 fails two lease checks (a stale worker, or one that does not hold the job, must get `LeaseError`; the task sends the model to the module docstring for the rules), t17 fails three redaction details (spacing after `Bearer` is kept, the user names `root` and `x` are not replaced). These look like model errors on stated rules, but the t15 and t17 rules were not all matched against the task wording. One run per task; no repeat.
**Mistake in the process.** The first launch was lost because the shell ended; a second, overlapping run was spoilt when its folder was deleted while it ran (all tasks then ended in 25 s with nothing delivered). Those two runs are void and not reported.
