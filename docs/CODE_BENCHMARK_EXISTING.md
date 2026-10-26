# Existing-codebase benchmark (TODO C22)

Ten coding challenges inside code DebCraft did not write. It complements `docs/CODE_BENCHMARK.md` (C1: fresh small tasks) and measures the
Mode A path: a repo copy, on-demand search (D-156), changed files delivered, the original never written.
Status 2026-10-27: challenges, pass checks, seeded patches and runner are built and validated offline (`selftest`, below). No live run has been done; a live run spends Azure tokens and needs the user's OK.

## Repositories (pinned; the clones are only read)
| Repo | Where | Pinned | Licence | Used for |
|---|---|---|---|---|
| pallets/click 8.1.8 | `c:\Work\Projects\Forge-benchmark-repos\click` | d4ecb8a | BSD-3 | challenges E01-E06: pure-Python library, no services |
| fastapi/full-stack-fastapi-template | `c:\Work\Projects\Forge-benchmark-repos\fastapi-template` | f4bcfab | MIT | challenges T01-T04: FastAPI + SQLModel + Alembic backend |

Baselines:
- click (py3.13, `.venv-click`): needs `pytest<9` (pytest 9 fails at collection on click's parametrize iterators). 636 passed, 12 skipped, 1 xfailed and **one failure that is already there**: `tests/test_utils.py::test_filename_formatting` (UnicodeDecodeError on Windows). The harness lists it as a known baseline failure and does not count it against the model.
- template: its own suite needs Postgres, so it is **not** part of the automatic score. The template challenges are checked by small pytest files that run the real app (routes, models, crud) against in-memory SQLite, so no database is needed. The interpreter must have the backend dependencies (the template asks for Python 3.14); pass it with `--template-python`. To also run the template's own suite, do it by hand on the delivered `backend` folder with `DATABASE_URL` pointing at the local Postgres, using a `forge_*` schema only.

## The ten challenges
Briefs are what the model gets (plus the standing line that `pip install` into the project environment is approved). File names appear in a brief only where a real user would give them.

| Id | Repo | Tier | Challenge | Real files (expected) | Pass check |
|---|---|---|---|---|---|
| E01 | click | small feature | `click.BOOL` also accepts `enable`, `enabled`, `disable`, `disabled`; tests and a changelog line | `src/click/types.py` (`BoolParamType.convert`), `tests/test_types.py`, `CHANGES.rst` | `check_e01.py`: new words in any case with spaces, every old word, unknown word error text unchanged, through a CLI option |
| E02 | click | seeded bug | Short help is cut with `...` when the text is exactly the limit (seed: `>` became `>=` in `make_default_short_help`) | `src/click/utils.py`, `tests/test_utils.py` | `check_e02.py`: 45-char text kept at limit 45, 46-char truncated, other truncation rules unchanged; the existing suite does NOT catch the seed (checked), so the model has to reproduce it itself |
| E03 | click | missing test | Tests for `join_options`, `measure_table`, `iter_rows`; source must not change | `src/click/formatting.py`, `tests/test_formatting.py` | mutation check: the delivered tests must pass on the source and fail on at least 5 of 6 planted mutants (sort order, slash flag, join string, max/min, column order, padding) |
| E04 | click | refactor, tests green | Share one helper for "write prompt, read line, Ctrl-C/EOF to Abort" between `prompt()` and `confirm()` | `src/click/termui.py`, `tests/test_termui.py`, `tests/test_utils.py` | `check_e04.py`: AST shows a module-level helper used by both and the handler count down from 3 to at most 2; behaviour tests (abort on EOF, hidden prompt prints a newline, visible one does not); existing suite stays green |
| E05 | click | dependency / API upgrade | Drop Python 3.7: minimum 3.8, remove the `importlib_metadata` fallback and its dependency; `version_option` keeps working | `src/click/decorators.py` (`version_option`), `pyproject.toml`, `CHANGES.rst` (bonus: `tox.ini`, `requirements/tests37.txt`, CI matrix) | `check_e05.py`: no backport import, no `importlib-metadata` in `pyproject.toml`, `requires-python` >= 3.8, `--version` works, missing-package error unchanged |
| E06 | click | performance | `Choice.convert` rebuilds a dict of all choices on every call: 3000 conversions against 20000 choices take seconds | `src/click/types.py` (`Choice.convert`), `tests/test_types.py` | `check_e06.py`: 3000 conversions on 20000 choices (exact and case-insensitive) each under 1.0 s; same results, same error text, `token_normalize_func` still applied |
| T01 | template | security / error handling | Seed: `read_item` lost its owner check, so any user can open another user's item. The model must find it, fix it, add a test | `backend/app/api/routes/items.py` (`read_item`), `backend/tests/api/routes/test_items.py` | `check_t01.py` (SQLite, real routes): other user gets 403 on read, update and delete; owner and superuser 200; unknown id 404; list shows own items only |
| T02 | template | type-hint / doc pass | `app/crud.py`: no `Any` returns (`update_user` returns `User`), a docstring on every public function, no behaviour change, mypy errors on `crud.py` and `utils.py` not above the baseline | `backend/app/crud.py`, `backend/app/utils.py` | `check_t02.py` (AST + behaviour of `update_user`, `authenticate`) plus a mypy error count compared with the baseline (when mypy is installed) |
| T03 | template | multi-file change | Items get `updated_at`: set on create, refreshed on API update, returned in responses, with an Alembic migration and tests | `backend/app/models.py`, `backend/app/api/routes/items.py`, new file in `backend/app/alembic/versions/` (after head `fe56fa70289e`), `backend/tests/api/routes/test_items.py` | `check_t03.py`: `ItemPublic` has the field, create gives a value, PUT moves it forward and keeps `created_at`, exactly one migration head and it adds `item.updated_at` on top of `fe56fa70289e`; at least one new test |
| T04 | template | vague brief, needs exploring | "The same person can end up with two accounts if they type their email differently. Look into it and fix whatever is wrong." Real cause: `crud.get_user_by_email` compares case-sensitively and `create_user` stores the email as typed | `backend/app/crud.py`, `backend/app/api/routes/users.py`, `backend/app/api/routes/login.py` | `check_t04.py`: sign-up in another letter case is refused (400), lookup and login ignore case, changing your own email to a taken one in other case gives 409, exact duplicates and unknown users still behave |

Split: six on click, four on the template; the vague brief and the cross-file change are on the template, as planned.

## Scoring fields (one row per challenge, in `result.json`)
| Field | How it is measured |
|---|---|
| right files found | expected files that appear in the model's read, search or edit calls (from `events.jsonl`), as `n/m`; also the number of tool calls before the first expected file and before the first edit |
| changed files delivered | added, modified and deleted files against a hash snapshot taken right after the seed was applied; `expected_files_changed` and `source_files_changed` |
| existing tests still pass | click: the repo's own suite in the delivered copy, new failures only (the known `test_filename_formatting` failure is reported apart). Template: "not run" unless you run it by hand |
| new tests added | count of `def test_` added in changed or new test files |
| pass check | the model-independent check for the challenge: pass, fail, or skipped (template interpreter missing) |
| time | seconds from the first to the last event, or `--seconds` |
| cost | `--cost` from the run's cost counter (USD) |
| where it got lost | automatic hints (failed tool calls, calls before the first expected file) plus your note via `--where-lost` |

A challenge **passes** when the pass check passes, the existing tests have no new failures, and the challenge's extra rules hold (E03: no source change, at least 5 of 6 mutants caught, and new tests; T03: new tests; T02: mypy not worse).

## Running it (no model involved until the live step)
All from the Forge repo, PowerShell. The checks for click use `C:\Work\Projects\Forge-benchmark-repos\.venv-click` (needs `pytest<9`); the template checks need `--template-python <python with the backend dependencies>`.
```
.venv\Scripts\python scripts\dev\run_existing_codebase_bench.py list
.venv\Scripts\python scripts\dev\run_existing_codebase_bench.py selftest                         # every check fails before and passes on a known solution
.venv\Scripts\python scripts\dev\run_existing_codebase_bench.py prepare E02 --run-name try1
```
`prepare` copies the pinned clone to `C:\Work\ForgeRuns\existing\try1\E02\repo`, applies the seeded bug, snapshots the files, runs the baseline checks (the pass check must fail first; it warns otherwise) and prints the exact commands for the live step. They use the same environment variables and driver as `scripts/benchmark/run_challenges.py`:
```
$env:FORGE_HOME = "C:\Work\ForgeRuns\existing\try1\E02\home"; $env:FORGE_ENV_FILE = "<forge repo>\.env"; $env:PYTHONIOENCODING = "utf-8"
.venv\Scripts\python -m forge.cli new --repo "...\E02\repo" --project existing-e02 --workspace "...\E02\workspace" --app-folder "."
.venv\Scripts\python scripts\campaign\drive_forge.py "...\E02\workspace" "...\E02\prompt.txt" "...\E02\run.json"
.venv\Scripts\python scripts\dev\run_existing_codebase_bench.py evaluate E02 --run-dir "...\E02" [--cost 0.31 --where-lost "..."]
```
`--app-folder` is `.` for click and `backend` for the template; if `forge new` rejects `.` for click, use `src`. `evaluate` scores `<run-dir>\workspace\repo` (the Mode A working copy; override with `--delivered`), prints one line and writes `result.json`. Run each challenge from a fresh `prepare`. Paste the table of results into `docs/CODE_BENCHMARK.md` next to C1.

## How the checks are kept honest
- Every check carries a first test that the imported code comes from the delivered copy, not from another install.
- `selftest` applies a known solution (`reference` edits and files in `scripts/dev/existing_bench/`) and requires: check fails before, passes after. Validated 2026-10-27 for all ten (click with `.venv-click`; template with a scratch Python 3.14 venv).
- The checks never fix how the model reads input, names helpers or lays out files, except where the brief asks (E04 helper, T03 migration).
- Files: `scripts/dev/run_existing_codebase_bench.py`, `scripts/dev/existing_bench/{harness,challenges,template_references}.py`, `scripts/dev/existing_bench/checks/`, `tests/test_existing_bench.py`.

## Open
- No live run yet. First run: E02 and T01 (small, seeded) to see how the harness and the Mode A copy behave, then the rest.
- `forge new --app-folder .` for click is untested against the CLI.
- Cost is passed by hand (`--cost`); the event log's cost field name has not been checked.
- The template's own Postgres suite is not automated.
