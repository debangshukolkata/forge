"""Checks Forge could not run itself (spec §9.5.2 "server-run"): DB-dependent tests delivered with exact
instructions for whoever has access. Stored in .forge/server_run.json; listed in output/SERVER_RUN.md and
in the final report as NOT run — Forge never implies verification it didn't do."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from forge.workspace.workspace import Workspace


class ServerRunCheck(BaseModel):
    tests: str  # pytest node ids or a selector, e.g. tests/test_policies_repo.py
    reason: str  # why Forge couldn't run it (e.g. "no write access to any database (L2/L1)")
    command: str  # exact command to run, from the app folder
    expected: str  # what a pass looks like / what to paste back


_LIST = TypeAdapter(list[ServerRunCheck])


def _path(workspace: Workspace) -> Path:
    return workspace.forge_dir / "server_run.json"


def load_checks(workspace: Workspace) -> list[ServerRunCheck]:
    path = _path(workspace)
    return _LIST.validate_json(path.read_text(encoding="utf-8")) if path.exists() else []


def add_check(workspace: Workspace, check: ServerRunCheck) -> list[ServerRunCheck]:
    checks = [c for c in load_checks(workspace) if c.tests != check.tests] + [check]
    path = workspace.jail.check(_path(workspace))
    path.write_bytes(_LIST.dump_json(checks, indent=1))
    return checks


def server_run_md(checks: list[ServerRunCheck], app_subfolder: str) -> str:
    lines = [
        "# Checks Forge could not run (server-run)",
        "",
        "These tests need database access Forge didn't have. They were NOT run. Run them once you're "
        f"connected, from `{app_subfolder}` with your venv active, and tell Forge the result (a pass/fail "
        "summary; never data rows).",
        "",
    ]
    for number, check in enumerate(checks, 1):
        lines += [
            f"## {number}. {check.tests}",
            "",
            f"- Why not run: {check.reason}",
            f"- Command: `{check.command}`",
            f"- Expected: {check.expected}",
            "",
        ]
    return "\n".join(lines)
