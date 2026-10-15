"""C14, D-417: a skill can be switched off for a process, and the A/B report compares two runs."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from forge.parity.skills import discover

RUNNER = Path(__file__).resolve().parent.parent / "scripts" / "benchmark" / "run_skill_ab.py"


def load_runner():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("run_skill_ab", RUNNER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_skill_ab"] = module
    spec.loader.exec_module(module)
    return module


def test_a_disabled_skill_is_neither_listed_nor_loadable(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "test-first" in discover()
    monkeypatch.setenv("FORGE_DISABLED_SKILLS", "test-first, pytest-patterns")
    skills = discover()
    assert "test-first" not in skills and "pytest-patterns" not in skills and "debugging" in skills


def row(task: str, passed: int, total: int, calls: int, wall: float, cost: float) -> dict[str, object]:
    return {
        "id": task,
        "hidden_passed": passed,
        "hidden_total": total,
        "hidden_failed": total - passed,
        "model_calls": calls,
        "wall_s": wall,
        "cost_usd": cost,
    }


def test_the_comparison_names_the_skill_and_says_which_condition_did_better() -> None:
    runner = load_runner()
    with_rows = [row("t1", 10, 10, 8, 100, 0.2), row("t2", 9, 10, 9, 120, 0.3)]
    without_rows = [row("t1", 10, 10, 6, 80, 0.15), row("t2", 7, 10, 7, 90, 0.2)]
    report = runner.compare("test-first", with_rows, without_rows)
    assert (
        "Skill `test-first`" in report
        and "1/2" in report
        and "2/2" not in report.split("without the skill")[0]
    )
    assert "The skill helped" in report and "Calls +4" in report
    assert "t2 | 9/10" in report
    flat = runner.compare("x", without_rows, with_rows)
    assert "The skill did not help" in flat
