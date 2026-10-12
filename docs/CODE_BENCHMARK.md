# Coding benchmark (TODO C1)

Measures how good the code DebCraft writes is, on the real model, so every change in TODO section 5b can be judged by numbers.
Status 2026-10-13: ten tasks and the runner are built and validated offline. Only a one-task smoke run has been made live (t01, below); the full baseline spends Azure
tokens, so run it when you are ready (see below).

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
