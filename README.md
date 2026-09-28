# Forge

A local, Windows-first coding agent that behaves like Claude Code, powered by Azure OpenAI.
It works in a per-requirement workspace and never edits your repository; it delivers only the
changed files plus instructions for copying them in.

- Specification: [docs/FORGE_BUILD_SPEC.md](docs/FORGE_BUILD_SPEC.md)
- Decisions: [docs/DECISIONS.md](docs/DECISIONS.md) · Risks: [docs/RISKS.md](docs/RISKS.md)
- Build conventions: [CLAUDE.md](CLAUDE.md) · Progress: [TODO.md](TODO.md)

## Development setup (Windows, Python 3.13)

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
Copy-Item .env.example .env        # then fill in values
powershell -ExecutionPolicy Bypass -File scripts\dev\setup_fixture_venv.ps1
```

## Checks

```powershell
.\.venv\Scripts\python -m pytest -q                 # offline suite
.\.venv\Scripts\python -m pytest -q -m live         # calls Azure OpenAI
.\.venv\Scripts\python -m ruff check .
.\.venv\Scripts\python -m ruff format --check .
.\.venv\Scripts\python -m mypy
.\.venv\Scripts\python scripts\check_secrets.py     # secret-leak scan
```
