---
id: skel-python-cli
type: skeleton
title: Python command line tool
summary: "An argparse CLI: `main(argv) -> int` for testing, `python -m` entry point, console script, tests with capsys, plus the package basics."
moods: [python, cli]
products: [cli, command line, tool, script]
tags: [python, argparse, pytest]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python-project skeletons, 2026-10-13)
tested: "ruff check, ruff format --check, mypy --strict and pytest all pass on a fresh copy (tests/test_python_skeletons.py)"
files:
  - from: templates/python-cli/pyproject.toml.tmpl
    to: pyproject.toml
  - from: templates/python-cli/README.md.tmpl
    to: README.md
  - from: templates/python-package/gitignore.tmpl
    to: .gitignore
  - from: templates/python-package/ci.yml.tmpl
    to: .github/workflows/ci.yml
  - from: templates/python-package/__init__.py.tmpl
    to: src/{{package}}/__init__.py
  - from: templates/python-package/py.typed.tmpl
    to: src/{{package}}/py.typed
  - from: templates/python-cli/cli.py.tmpl
    to: src/{{package}}/cli.py
  - from: templates/python-cli/__main__.py.tmpl
    to: src/{{package}}/__main__.py
  - from: templates/python-cli/test_cli.py.tmpl
    to: tests/test_cli.py
---

## Python command line tool

Pass `variables`: `package` (the importable snake_case name, e.g. `inventory_tool`) and `description` (one line).

`main(argv)` returns the exit code (0 success, 2 bad usage) and is what the tests call; the console script is `{{package}}` after `pip install -e .`. Add options in `build_parser`.
