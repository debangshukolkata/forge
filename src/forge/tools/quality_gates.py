"""Automatic quality gates on the code DebCraft wrote (TODO C2, D-295). Before a task may be called done, the files DebCraft changed are
checked with the usual tools: ruff (real bugs, unused names, mutable defaults, over-complex functions), mypy when the project
configures it, bandit (security) when it is installed. Findings go back to the model like the import check does. Only the project's own
files that DebCraft wrote are looked at; a tool that is not installed is skipped silently (never a blocker); a project can turn gates off
or tune them in `.forge/gates.json`. Never raises."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from forge.tools.test_quality import weak_test_findings

TIMEOUT_S = 90
MAX_SHOWN = 10
MAX_PER_TOOL = 8
MAX_COMPLEXITY = 15
RUFF_DEFAULT_RULES = "E9,F,B006,B904,C901"  # syntax errors, pyflakes, mutable defaults, raise-from, complexity; not B008: FastAPI and Typer use calls in defaults on purpose
BANDIT_SKIPS = "B101,B311"  # assert in tests, random for non-crypto use
MYPY_CONFIG_FILES = ("mypy.ini", ".mypy.ini")
RUFF_CONFIG_FILES = ("ruff.toml", ".ruff.toml")


@dataclass(frozen=True)
class GateConfig:
    enabled: bool = True
    ruff: bool = True
    mypy: bool = True
    bandit: bool = True
    tests: bool = True  # tests that cannot fail (no assertion, assert True, only mocks)
    bar: bool = True  # a check turned off to get to green (new suppression, skipped or deleted tests)
    max_complexity: int = MAX_COMPLEXITY


def load_config(forge_dir: Path) -> GateConfig:
    """`.forge/gates.json`: {"enabled": false} switches every gate off; each tool and `max_complexity` can be set. Bad files mean defaults."""
    try:
        data = json.loads((forge_dir / "gates.json").read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return GateConfig()
        defaults = GateConfig()
        return GateConfig(
            enabled=bool(data.get("enabled", defaults.enabled)),
            ruff=bool(data.get("ruff", defaults.ruff)),
            mypy=bool(data.get("mypy", defaults.mypy)),
            bandit=bool(data.get("bandit", defaults.bandit)),
            tests=bool(data.get("tests", defaults.tests)),
            bar=bool(data.get("bar", defaults.bar)),
            max_complexity=int(data.get("max_complexity", defaults.max_complexity)),
        )
    except (OSError, ValueError, TypeError):
        return GateConfig()


def _run(
    command: list[str], cwd: Path, env: dict[str, str] | None
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command, cwd=cwd, env=env, capture_output=True, text=True, timeout=TIMEOUT_S, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _has_module(python: str, module: str, cwd: Path, env: dict[str, str] | None) -> bool:
    done = _run([python, "-c", f"import {module}"], cwd, env)
    return done is not None and done.returncode == 0


def _project_text(root: Path, name: str) -> str:
    try:
        return (root / name).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _configures(root: Path, tool: str) -> bool:
    if tool == "mypy":
        return (
            any((root / f).exists() for f in MYPY_CONFIG_FILES)
            or "[tool.mypy]" in _project_text(root, "pyproject.toml")
            or "[mypy]" in _project_text(root, "setup.cfg")
        )
    return any((root / f).exists() for f in RUFF_CONFIG_FILES) or "[tool.ruff" in _project_text(
        root, "pyproject.toml"
    )


def _relative(path: str, root: Path) -> str:
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return path.replace("\\", "/")


def _ruff(
    files: list[str], root: Path, python: str, env: dict[str, str] | None, config: GateConfig
) -> list[str]:
    # The workspace's own ruff when it has one, else DebCraft's (a development install); neither: skipped.
    interpreter = next((p for p in (python, sys.executable) if _has_module(p, "ruff", root, env)), None)
    if interpreter is None:
        return []
    command = [interpreter, "-m", "ruff", "check", "--no-cache", "--output-format", "concise"]
    if not _configures(
        root, "ruff"
    ):  # the project's own rules win; without any, a short list of real problems
        command += [
            "--isolated",
            "--select",
            RUFF_DEFAULT_RULES,
            "--config",
            f"lint.mccabe.max-complexity = {config.max_complexity}",
        ]
    done = _run([*command, *files], root, env)
    if done is None:
        return []
    found = []
    for line in done.stdout.splitlines():
        match = re.match(r"^(.+?):(\d+):\d+: (\S+) (.*)$", line)
        if match:
            found.append(f"ruff: {_relative(match[1], root)}:{match[2]}: {match[3]} {match[4]}")
    return found


def _mypy(files: list[str], root: Path, python: str, env: dict[str, str] | None) -> list[str]:
    if not _configures(root, "mypy") or not _has_module(python, "mypy", root, env):
        return []
    done = _run(
        [python, "-m", "mypy", "--no-error-summary", "--no-color-output", "--no-pretty", *files], root, env
    )
    if done is None:
        return []
    found = []
    for line in done.stdout.splitlines():
        match = re.match(r"^(.+?):(\d+): error: (.*)$", line)
        if match:
            found.append(f"mypy: {_relative(match[1], root)}:{match[2]}: {match[3]}")
    return found


def _bandit(files: list[str], root: Path, python: str, env: dict[str, str] | None) -> list[str]:
    if not _has_module(python, "bandit", root, env):
        return []
    done = _run([python, "-m", "bandit", "-q", "-f", "json", "-ll", "-s", BANDIT_SKIPS, *files], root, env)
    if done is None or not done.stdout.strip():
        return []
    try:
        results = json.loads(done.stdout).get("results", [])
    except ValueError:
        return []
    return [
        f"bandit: {_relative(item['filename'], root)}:{item['line_number']}: {item['test_id']} {item['issue_text']} (severity {item['issue_severity'].lower()})"
        for item in results
    ]


def gate_findings(
    files: set[Path], root: Path, python: str, env: dict[str, str] | None, config: GateConfig
) -> list[str]:
    """Findings in the given Python files; empty when gates are off, no tool is installed, or everything is clean."""
    selected = sorted(str(f) for f in files if f.suffix == ".py" and f.exists())
    if not config.enabled or not selected:
        return []
    found: list[str] = []
    if config.ruff:
        found += _ruff(selected, root, python, env, config)[:MAX_PER_TOOL]
    if config.mypy:
        found += _mypy(selected, root, python, env)[:MAX_PER_TOOL]
    if config.bandit:
        found += _bandit(selected, root, python, env)[:MAX_PER_TOOL]
    if config.tests:
        found += weak_test_findings([Path(f) for f in selected], root)[:MAX_PER_TOOL]
    return found


def gate_note(findings: list[str], round_number: int, last_round: int) -> str:
    shown = "\n".join(f"- {line}" for line in findings[:MAX_SHOWN])
    more = f"\n- ... and {len(findings) - MAX_SHOWN} more" if len(findings) > MAX_SHOWN else ""
    ending = (
        "Fix them and call task_update again. If a finding is wrong or accepted on purpose, fix what you can and say in the handoff "
        "note why the rest stays; the next call is accepted either way."
        if round_number >= last_round
        else "Fix them and call task_update again."
    )
    return f"Not accepted: the quality gates found problems in the code you wrote:\n{shown}{more}\n{ending}"
