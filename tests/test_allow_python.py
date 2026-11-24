"""D-649: "allow all Python in this project": what it covers, what it never covers, and who can switch it."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.engine.log_summary import approval_lines
from forge.protocol.events import Event, EventType
from forge.safety.permissions import PermissionGate, PermissionRules, Rule
from forge.safety.shell_classifier import ShellScope

COVERED = [
    "python app.py local",
    r".\.venv\Scripts\python app.py",
    'python -c "import os; print(1)"',
    "cd backend; python app.py",
    r"$env:PORT='5045'; $env:MODE=local; .\.venv\Scripts\python app.py local",
    "python app.py > out.txt",
    "python app.py | Select-Object -First 5",
    "python -m http.server 8000",
]
NEVER = [
    "python -m pip install flask",
    "python -c \"import requests; requests.get('https://dev.example.com')\"",
    "python -c \"print(open('.env').read())\"",
    "python ../../../other/x.py",
    "Remove-Item x.py; python app.py",
    "python app.py; git checkout .",
    "python $(Remove-Item x.py)",
    'python -c "$(Remove-Item x.py)"',
    "$env:PATH='C:\\evil'; python app.py",
    "$env:PYTHONPATH='x'; python app.py",
    "$env:X=$(Remove-Item y); python app.py",
    'powershell -Command "python x.py"',
    "node app.js; python app.py",
    "python x.py | ForEach-Object { Remove-Item $_ }",
    "npm run build",
]


def gate(tmp_path: Path, mode: str = "default", rules: PermissionRules | None = None) -> PermissionGate:
    return PermissionGate(mode, tmp_path / "permissions.json", rules)  # type: ignore[arg-type]


def verdict(g: PermissionGate, command: str, tmp_path: Path, tool: str = "run_command") -> str:
    workspace = tmp_path / "ws"
    (workspace / "repo" / "backend").mkdir(parents=True, exist_ok=True)
    scope = ShellScope(workspace_root=workspace, original_repo=tmp_path / "original", cwd=workspace / "repo")
    return g.decide(tool, False, command, scope).verdict


@pytest.mark.parametrize("command", COVERED)
def test_python_runs_once_allowed(command: str, tmp_path: Path) -> None:
    g = gate(tmp_path)
    assert verdict(g, command, tmp_path) == "ask"
    g.allow_python(True)
    assert verdict(g, command, tmp_path) == "allow"
    g.allow_python(False)
    assert verdict(g, command, tmp_path) == "ask"


@pytest.mark.parametrize("command", NEVER)
def test_everything_else_is_still_asked_about(command: str, tmp_path: Path) -> None:
    g = gate(tmp_path)
    g.allow_python(True)
    assert verdict(g, command, tmp_path) in ("ask", "deny")


def test_plan_mode_blocks_and_deny_rules_win(tmp_path: Path) -> None:
    g = gate(tmp_path, "plan")
    g.allow_python(True)
    assert verdict(g, "python app.py", tmp_path) == "deny"
    g = gate(tmp_path, rules=PermissionRules(deny=(Rule.parse("run_command(python*)"),)))
    assert verdict(g, "python app.py", tmp_path) == "deny"


def test_it_is_kept_beside_the_prefixes_and_for_this_project_only(tmp_path: Path) -> None:
    g = gate(tmp_path)
    g.allow_prefix("npm run build")
    g.allow_python(True)
    g.allow_prefix("npm test")
    assert json.loads((tmp_path / "permissions.json").read_text(encoding="utf-8")) == {
        "allowed_prefixes": ["npm run build", "npm test"],
        "allow_all_python": True,
    }
    assert not PermissionGate("default", tmp_path / "other" / "permissions.json").python_allowed()


def test_the_choice_is_offered_only_where_it_helps(tmp_path: Path) -> None:
    g = gate(tmp_path)
    scope = ShellScope(workspace_root=tmp_path, original_repo=None, cwd=tmp_path)
    assert g.decide("run_command", False, "python app.py", scope).offer_python
    for command in ("npm run build", "python -m pip install x", "python app.py; Remove-Item x"):
        assert not g.decide("run_command", False, command, scope).offer_python, command


def test_the_report_counts_the_cards_by_reason() -> None:
    def card(seq: int, **payload: object) -> Event:
        return Event(
            seq=seq, ts="2026-11-24T10:00:00+00:00", type=EventType.APPROVAL_REQUESTED, payload=payload
        )

    text = "\n".join(
        approval_lines(
            [
                card(1, tool="run_command", reason="installs packages", always_ask=True),
                card(2, tool="run_command", reason="installs packages", always_ask=True),
                card(3, tool="plan", reason="", markdown="# a plan"),
            ]
        )
    )
    assert "2x run_command: installs packages (asked in auto mode too)" in text and "plan" not in text
