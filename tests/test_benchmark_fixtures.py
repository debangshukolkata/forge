"""C1: the coding-benchmark tasks are valid. With the reference solution every hidden test passes and the seed's
own tests stay green; without it the hidden tests fail, so a task cannot be passed by doing nothing."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TASKS = Path(__file__).resolve().parent / "benchmarks" / "tasks"
TASK_IDS = sorted(p.name for p in TASKS.iterdir() if p.is_dir())


def _pytest(folder: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--rootdir", str(folder), "."],
        cwd=folder,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        env={**__import__("os").environ, "PYTHONPATH": str(folder)},
    )


def _assemble(task: Path, destination: Path, with_reference: bool) -> None:
    if (task / "seed").exists():
        shutil.copytree(task / "seed", destination, dirs_exist_ok=True)
    if with_reference:
        shutil.copytree(task / "reference", destination, dirs_exist_ok=True)
    shutil.copytree(task / "hidden", destination / "hidden_tests", dirs_exist_ok=True)


def test_there_are_ten_tasks_with_the_expected_files() -> None:
    assert len(TASK_IDS) >= 10
    for task_id in TASK_IDS:
        task = TASKS / task_id
        meta = json.loads((task / "task.json").read_text(encoding="utf-8"))
        assert meta["id"] == task_id and meta["tier"] and meta["entry"]
        assert (task / "task.md").read_text(encoding="utf-8").strip()
        assert (task / "reference" / meta["entry"]).exists()
        assert list((task / "hidden").glob("test_*.py"))


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_reference_solution_passes_everything(task_id: str, tmp_path: Path) -> None:
    _assemble(TASKS / task_id, tmp_path, with_reference=True)
    result = _pytest(tmp_path)
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-1000:]


@pytest.mark.parametrize("task_id", TASK_IDS)
def test_hidden_tests_fail_without_the_solution(task_id: str, tmp_path: Path) -> None:
    _assemble(TASKS / task_id, tmp_path, with_reference=False)
    hidden_only = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--rootdir",
            str(tmp_path),
            "hidden_tests",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        env={**__import__("os").environ, "PYTHONPATH": str(tmp_path)},
    )
    assert hidden_only.returncode != 0


def _runner_module():  # type: ignore[no-untyped-def]
    import importlib.util

    path = Path(__file__).resolve().parents[1] / "scripts" / "benchmark" / "run_code_benchmark.py"
    spec = importlib.util.spec_from_file_location("run_code_benchmark", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_scores_a_delivered_solution_and_ignores_the_models_own_tests(tmp_path: Path) -> None:
    runner = _runner_module()
    task = TASKS / "t01_slugify"
    workspace = tmp_path / "ws"
    (workspace / "project").mkdir(parents=True)
    shutil.copytree(task / "reference", workspace / "project", dirs_exist_ok=True)
    (workspace / "project" / "test_own.py").write_text(
        "def test_broken():\n    assert False\n", encoding="utf-8"
    )
    result = runner.score(workspace, task, "textutil.py", tmp_path / "scoring", python=Path(sys.executable))
    assert result["delivered"] is True
    assert result["hidden_failed"] == 0 and result["hidden_passed"] >= 10


def test_runner_reports_a_missing_delivery(tmp_path: Path) -> None:
    runner = _runner_module()
    (tmp_path / "ws" / "project").mkdir(parents=True)
    result = runner.score(
        tmp_path / "ws", TASKS / "t01_slugify", "textutil.py", tmp_path / "s", python=Path(sys.executable)
    )
    assert result["delivered"] is False
    table = runner.markdown("x", [{"id": "t01", "tier": "single function", **result, "wall_s": 3}])
    assert "not delivered" in table
