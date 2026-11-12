# DebCraft

A local, Windows-first coding agent that behaves like Claude Code, powered by Azure OpenAI.
It works in a per-requirement workspace and never edits your repository; it delivers only the
changed files plus instructions for copying them in.

What it is for: solving a requirement against an existing system. DebCraft learns the repository and keeps
that knowledge between projects, runs the application, finds what stops it from doing what is asked, fixes it
and proves the fix by running the same check again. It stays light: a small set of tools is always loaded, the
rest and the skills are loaded when a task needs them.

- Specification: [docs/FORGE_BUILD_SPEC.md](docs/FORGE_BUILD_SPEC.md)
- Decisions: [docs/DECISIONS.md](docs/DECISIONS.md) · Risks: [docs/RISKS.md](docs/RISKS.md)
- Build conventions: [CLAUDE.md](CLAUDE.md) · Progress: [TODO.md](TODO.md)
- Using it: [docs/INSTALL.md](docs/INSTALL.md) · Modules: [docs/MODULES.md](docs/MODULES.md)

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
