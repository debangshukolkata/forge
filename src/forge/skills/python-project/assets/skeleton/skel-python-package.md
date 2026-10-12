---
id: skel-python-package
type: skeleton
title: Python package (src layout)
summary: "A library project: pyproject.toml, src layout, typed, pytest, ruff, mypy strict, CI file and README."
moods: [python, library]
products: [library, package, utility]
tags: [python, pytest, ruff, mypy, typing]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python-project skeletons, 2026-10-13)
tested: "ruff check, ruff format --check, mypy --strict and pytest all pass on a fresh copy (tests/test_python_skeletons.py)"
files:
  - from: templates/python-package/pyproject.toml.tmpl
    to: pyproject.toml
  - from: templates/python-package/README.md.tmpl
    to: README.md
  - from: templates/python-package/gitignore.tmpl
    to: .gitignore
  - from: templates/python-package/ci.yml.tmpl
    to: .github/workflows/ci.yml
  - from: templates/python-package/__init__.py.tmpl
    to: src/{{package}}/__init__.py
  - from: templates/python-package/py.typed.tmpl
    to: src/{{package}}/py.typed
  - from: templates/python-package/core.py.tmpl
    to: src/{{package}}/core.py
  - from: templates/python-package/test_core.py.tmpl
    to: tests/test_core.py
---

## Python package (src layout)

Pass `variables`: `package` (the importable snake_case name, e.g. `inventory_tool`) and `description` (one line).

After adding: `python -m venv .venv`, `.venv\Scripts\python -m pip install -e ".[dev]"`, then run pytest, ruff and mypy. Replace `core.py` and its test with the real behaviour; keep the checks green. Tests run without installing (`pythonpath = ["src"]`).
