---
name: python-project
description: Start or structure a Python project (library, command line tool, async worker, REST service) from tested skeletons, and keep it clean. Use when creating a new Python project or when asked for a CLI, worker or API from scratch.
---
# Python projects that start clean

Starting from a blank folder invites the usual drift: no tests configured, no types, no lint, a flat pile of files. The
skeletons here are complete, small projects that pass `ruff`, `mypy --strict` and `pytest` as shipped.

1. `find_asset` with a few words ("python cli tool", "rest api service", "async worker", "library") and type `skeleton`.
2. `add_asset(id, project_dir, variables={"package": "<snake_case_name>", "description": "<one line>"})`. It copies the files
   (pyproject.toml, src layout, tests, README, .gitignore, CI file) and records the licence.
3. Create the virtual environment and install: `python -m venv .venv`, then `.venv\Scripts\python -m pip install -e ".[dev]"`
   (macOS/Linux: `.venv/bin/python`). Ask before installing if the permission prompt requires it.
4. Replace the example module and its test with the real behaviour. Keep the checks green as you go:
   `python -m pytest`, `python -m ruff check .`, `python -m ruff format --check .`, `python -m mypy`.

Rules the skeletons encode (keep them when you extend the project):
- Code under `src/<package>/`, tests under `tests/`; tests import the package, never the other way round.
- Type hints everywhere (`from __future__ import annotations`), `mypy --strict` clean; no bare `except:`; raise specific errors.
- Put the work in functions that take their inputs (`main(argv)`, `create_app()`), so tests can call them without a process or a server.
- One test per behaviour, with edge cases and the error path; expected values written by hand, not recomputed from the code.
- Dependencies go in `pyproject.toml` (runtime in `dependencies`, tools in the `dev` extra); do not leave an unused one.
