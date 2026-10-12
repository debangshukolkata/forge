---
id: skel-fastapi-service
type: skeleton
title: FastAPI service
summary: "A REST service: app factory, pydantic models with validation, a health check, create/read/list routes and TestClient tests."
moods: [python, api]
products: [rest api, service, backend, fastapi]
tags: [python, fastapi, pydantic, pytest]
density: any
dependencies: [fastapi, uvicorn, httpx]
licence: original
source: authored for DebCraft (python-project skeletons, 2026-10-13)
tested: "ruff check, ruff format --check, mypy --strict and pytest all pass on a fresh copy (tests/test_python_skeletons.py)"
files:
  - from: templates/fastapi-service/pyproject.toml.tmpl
    to: pyproject.toml
  - from: templates/fastapi-service/README.md.tmpl
    to: README.md
  - from: templates/python-package/gitignore.tmpl
    to: .gitignore
  - from: templates/python-package/ci.yml.tmpl
    to: .github/workflows/ci.yml
  - from: templates/python-package/__init__.py.tmpl
    to: src/{{package}}/__init__.py
  - from: templates/python-package/py.typed.tmpl
    to: src/{{package}}/py.typed
  - from: templates/fastapi-service/app.py.tmpl
    to: src/{{package}}/app.py
  - from: templates/fastapi-service/test_api.py.tmpl
    to: tests/test_api.py
---

## FastAPI service

Pass `variables`: `package` (the importable snake_case name, e.g. `inventory_tool`) and `description` (one line).

Install with `pip install -e ".[dev]"`. Run: `python -m uvicorn {{package}}.app:app --reload`. `create_app()` gives each test a fresh in-memory store; replace it with a real repository layer. Validation errors are 422, missing items 404.
