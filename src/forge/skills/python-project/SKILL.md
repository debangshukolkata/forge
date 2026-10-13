---
name: python-project
description: Use when you start a Python project (library, command line tool, async worker, REST service) or need a short tested recipe for errors, logging, settings, typing, async, tests, SQL, security or performance
---
# Python projects that start clean, and recipes for the usual problems

Starting from a blank folder invites the usual drift: no tests configured, no types, no lint, a flat pile of files. The
skeletons here are complete, small projects that pass `ruff`, `mypy --strict` and `pytest` as shipped. The recipes are
short, tested answers to problems that come up in nearly every project.

## Starting a project
1. `find_asset` with a few words ("python cli tool", "rest api service", "async worker", "library") and type `skeleton`.
2. `add_asset(id, project_dir, variables={"package": "<snake_case_name>", "description": "<one line>"})`. It copies the files
   (pyproject.toml, src layout, tests, README, .gitignore, CI file) and records the licence.
3. Install the project into the environment: in a DebCraft workspace the virtual environment already exists, so run
   `python -m pip install -e ".[dev]"` (the permission prompt asks). Outside one: `python -m venv .venv` first. The tests
   also run without installing (`pythonpath = ["src"]`).
4. Replace the example module and its test with the real behaviour. Keep the checks green as you go:
   `python -m pytest`, `python -m ruff check .`, `python -m ruff format --check .`, `python -m mypy`.

## Looking up a recipe
`find_asset` with the topic and type `recipe` ("error handling", "logging", "settings environment", "typing protocol",
"asyncio timeout", "pytest fixtures", "sql injection", "security checklist", "performance", "refactoring", "cli exit
codes", "python 3.12 features"); then `add_asset(id)` returns the text (nothing is copied for a recipe). Every code block
marked `# runnable` is executed by the test suite, so the examples work. Read the recipe before writing that part of the
code, and when you review your own code run through `rcp-security` for anything that takes outside input.

## Rules the skeletons and recipes encode (keep them when you extend the project)
- Code under `src/<package>/`, tests under `tests/`; tests import the package, never the other way round.
- Type hints everywhere (`from __future__ import annotations`), `mypy --strict` clean; no bare `except:`; raise specific errors.
- Put the work in functions that take their inputs (`main(argv)`, `create_app()`), so tests can call them without a process or a server.
- One test per behaviour, with edge cases and the error path; expected values written by hand, not recomputed from the code.
- Dependencies go in `pyproject.toml` (runtime in `dependencies`, tools in the `dev` extra); do not leave an unused one.
- Before using a library you do not know well, check the installed version (`python -m pip show <package>`) and read its docs.

## Gotchas
- `from __future__ import annotations` first, type hints everywhere, errors as specific exception classes.
