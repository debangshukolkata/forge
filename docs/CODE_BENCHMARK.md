# Coding benchmark (TODO C1)

Measures how good the code DebCraft writes is, on the real model, so every change in TODO section 5b can be judged by numbers.
Status 2026-10-13: ten tasks and the runner are built and validated offline; the first full baseline is below.

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

Each task folder holds `task.md` (the prompt DebCraft gets), `task.json` (id, tier, entry module), `seed/` (files the "user" already
has, put in the workspace's `project/` folder), `hidden/` (tests DebCraft never sees) and `reference/` (a solution that proves the task
is solvable). `tests/test_benchmark_fixtures.py` checks, in the normal suite and without any model, that the reference passes every
hidden test and the seed's own tests, and that the hidden tests fail without the reference.

## Not covered yet (add before the benchmark is "complete")
REST API service (needs a framework install), a Mode A repository task, a Mode B task with no host code at all, a larger multi-file
feature, and the judge rubric (below). Aim: 20 to 30 tasks.

## Running it
```
.venv\Scripts\python scripts\benchmark\run_code_benchmark.py baseline-2026-10-14
.venv\Scripts\python scripts\benchmark\run_code_benchmark.py try-x --tasks t01_slugify,t04_paginate_bug --env SOME_SETTING=1
```
Work is under `C:\Work\ForgeRuns\codebench\<run-name>` (one workspace per task, an isolated DebCraft home, `results.json`,
`results.md`). The runner scores the delivered module with the hidden tests (the model's own test files are left out of scoring), and
records wall time, model calls, tool seconds, seconds waited for approvals, tokens and cost. Paste the table below with the date and
what changed.

## Judge rubric (manual for now)
Read the delivered code and score 1 to 5: correctness, edge cases, error handling, tests that prove something, security, simplicity,
readability. An automatic judge (a different model) comes after the first manual scores show whether it agrees with you.

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
