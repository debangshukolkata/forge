---
id: skel-async-worker
type: skeleton
title: Async worker pool
summary: "An asyncio worker pool: a queue, N workers, failure isolation and a graceful stop, with tests that need no plugin."
moods: [python, async]
products: [worker, queue, background jobs, async]
tags: [python, asyncio, queue]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python-project skeletons, 2026-10-13)
tested: "ruff check, ruff format --check, mypy --strict and pytest all pass on a fresh copy (tests/test_python_skeletons.py)"
files:
  - from: templates/async-worker/pyproject.toml.tmpl
    to: pyproject.toml
  - from: templates/async-worker/README.md.tmpl
    to: README.md
  - from: templates/python-package/gitignore.tmpl
    to: .gitignore
  - from: templates/python-package/ci.yml.tmpl
    to: .github/workflows/ci.yml
  - from: templates/python-package/__init__.py.tmpl
    to: src/{{package}}/__init__.py
  - from: templates/python-package/py.typed.tmpl
    to: src/{{package}}/py.typed
  - from: templates/async-worker/worker.py.tmpl
    to: src/{{package}}/worker.py
  - from: templates/async-worker/test_worker.py.tmpl
    to: tests/test_worker.py
---

## Async worker pool

Pass `variables`: `package` (the importable snake_case name, e.g. `inventory_tool`) and `description` (one line).

`WorkerPool(workers)`: `await start()`, `await submit(job)` (a zero-argument async callable), `await stop()` (finishes queued jobs). A failing job is logged and counted in `failed`; it never stops the other workers.
