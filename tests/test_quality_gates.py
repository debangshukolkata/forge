"""C2: quality gates on the code DebCraft wrote (ruff, mypy when configured, bandit when installed), and how they send a task back."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from forge.tools.quality_gates import GateConfig, gate_findings, gate_note, load_config

PY = sys.executable
HAS_RUFF = importlib.util.find_spec("ruff") is not None
HAS_BANDIT = importlib.util.find_spec("bandit") is not None

BUGGY = """import os


def add(item, items=[]):
    items.append(item)
    return items
"""

COMPLEX = (
    "def f(x):\n" + "".join(f"    if x == {i}:\n        return {i}\n" for i in range(20)) + "    return -1\n"
)


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.skipif(not HAS_RUFF, reason="ruff is not installed here")
def test_ruff_finds_unused_imports_and_mutable_defaults(tmp_path: Path) -> None:
    file = _write(tmp_path, "app.py", BUGGY)
    found = gate_findings({file}, tmp_path, PY, None, GateConfig(mypy=False, bandit=False))
    text = "\n".join(found)
    assert "app.py:1: F401" in text and "B006" in text
    assert all(line.startswith("ruff: ") for line in found)


@pytest.mark.skipif(not HAS_RUFF, reason="ruff is not installed here")
def test_complex_functions_are_flagged_and_the_limit_is_configurable(tmp_path: Path) -> None:
    file = _write(tmp_path, "big.py", COMPLEX)
    assert any(
        "C901" in line
        for line in gate_findings({file}, tmp_path, PY, None, GateConfig(mypy=False, bandit=False))
    )
    relaxed = GateConfig(mypy=False, bandit=False, max_complexity=40)
    assert not any("C901" in line for line in gate_findings({file}, tmp_path, PY, None, relaxed))


@pytest.mark.skipif(not HAS_RUFF, reason="ruff is not installed here")
def test_clean_code_has_no_findings(tmp_path: Path) -> None:
    file = _write(tmp_path, "ok.py", "def add(a: int, b: int) -> int:\n    return a + b\n")
    assert gate_findings({file}, tmp_path, PY, None, GateConfig()) == []


@pytest.mark.skipif(not HAS_RUFF, reason="ruff is not installed here")
def test_the_projects_own_ruff_rules_win(tmp_path: Path) -> None:
    (tmp_path / "ruff.toml").write_text('[lint]\nselect = ["E9"]\n', encoding="utf-8")  # only syntax errors
    file = _write(tmp_path, "app.py", BUGGY)
    assert gate_findings({file}, tmp_path, PY, None, GateConfig(mypy=False, bandit=False)) == []


def test_mypy_only_runs_when_the_project_configures_it(tmp_path: Path) -> None:
    pytest.importorskip("mypy")
    file = _write(tmp_path, "typed.py", "def f(x: int) -> str:\n    return x\n")
    off = GateConfig(ruff=False, bandit=False)
    assert gate_findings({file}, tmp_path, PY, None, off) == []
    (tmp_path / "mypy.ini").write_text("[mypy]\n", encoding="utf-8")
    found = gate_findings({file}, tmp_path, PY, None, off)
    assert found and found[0].startswith("mypy: typed.py:2:")


@pytest.mark.skipif(not HAS_BANDIT, reason="bandit is not installed here")
def test_bandit_flags_shell_injection(tmp_path: Path) -> None:
    file = _write(
        tmp_path, "run.py", "import subprocess\n\n\ndef go(cmd):\n    subprocess.call(cmd, shell=True)\n"
    )
    found = gate_findings({file}, tmp_path, PY, None, GateConfig(ruff=False, mypy=False))
    assert found and "B602" in found[0]


def test_nothing_is_checked_when_gates_are_off_or_no_python_file_changed(tmp_path: Path) -> None:
    file = _write(tmp_path, "app.py", BUGGY)
    assert gate_findings({file}, tmp_path, PY, None, GateConfig(enabled=False)) == []
    notes = _write(tmp_path, "notes.md", "# x")
    assert gate_findings({notes}, tmp_path, PY, None, GateConfig()) == []
    assert gate_findings(set(), tmp_path, PY, None, GateConfig()) == []


def test_a_missing_tool_is_skipped_not_an_error(tmp_path: Path) -> None:
    file = _write(tmp_path, "app.py", BUGGY)
    # an interpreter that does not exist: every tool is "not installed", nothing raises
    assert (
        gate_findings({file}, tmp_path, str(tmp_path / "no-python.exe"), None, GateConfig(ruff=False)) == []
    )


def test_config_file_switches_and_tolerates_bad_json(tmp_path: Path) -> None:
    assert load_config(tmp_path) == GateConfig()
    (tmp_path / "gates.json").write_text(
        json.dumps({"enabled": False, "max_complexity": 8, "bandit": False}), encoding="utf-8"
    )
    config = load_config(tmp_path)
    assert (config.enabled, config.max_complexity, config.bandit, config.ruff) == (False, 8, False, True)
    (tmp_path / "gates.json").write_text("{not json", encoding="utf-8")
    assert load_config(tmp_path) == GateConfig()


def test_the_note_lists_findings_and_the_last_round_says_the_next_call_is_accepted() -> None:
    findings = [f"ruff: a.py:{i}: F401 unused" for i in range(14)]
    first = gate_note(findings, 1, 2)
    last = gate_note(findings, 2, 2)
    assert "a.py:0" in first and "and 4 more" in first and "accepted either way" not in first
    assert "accepted either way" in last


@pytest.mark.skipif(not HAS_RUFF, reason="ruff is not installed here")
def test_fastapi_style_calls_in_defaults_are_not_flagged(tmp_path: Path) -> None:
    """speed-3: the gate sent a FastAPI app back for `db = Depends(get_db)` (B008), a false positive for the idiom."""
    code = "from fastapi import Depends, FastAPI\n\napp = FastAPI()\n\n\ndef get_db() -> int:\n    return 1\n\n\n@app.get('/')\ndef read(db: int = Depends(get_db)) -> int:\n    return db\n"
    file = _write(tmp_path, "api.py", code)
    assert gate_findings({file}, tmp_path, PY, None, GateConfig(mypy=False, bandit=False)) == []
