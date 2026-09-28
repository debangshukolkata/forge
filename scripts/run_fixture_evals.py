"""Runs Forge on the realistic fixture tasks in evals/fixture_tasks/ (spec M11) and scores each one with its
hidden acceptance test, which Forge never sees: it is copied into the workspace only after the run.

Usage (live: uses the Azure deployment in Forge's .env):
    .venv\\Scripts\\python scripts\\run_fixture_evals.py                 # all tasks
    .venv\\Scripts\\python scripts\\run_fixture_evals.py 01_claims_stats  # some tasks

Per task it records: Forge's exit code and final phase, whether the hidden test passes, whether the fixture's
whole suite (old + Forge's new tests + hidden) passes, and the duration. The report goes to
test-artifacts/evals-<timestamp>/REPORT.md with each workspace kept next to it for inspection.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS = REPO_ROOT / "evals" / "fixture_tasks"
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample_repo"
FIXTURE_PYTHON = FIXTURE / "backend" / "venv" / "Scripts" / "python.exe"
FORGE = REPO_ROOT / ".venv" / "Scripts" / "forge.exe"
RUN_TIMEOUT_S = 60 * 60


def run_task(name: str, out: Path) -> dict[str, object]:
    task = yaml.safe_load((TASKS / name / "task.yaml").read_text(encoding="utf-8"))
    app_folder = task.get("app_folder", "backend")
    workspace = out / name / "ws"
    env = {
        **os.environ,
        "FORGE_HOME": str(out / name / "forge_home"),
        "FORGE_ENV_FILE": str(REPO_ROOT / ".env"),
    }
    started = time.monotonic()
    subprocess.run(
        [
            str(FORGE),
            "new",
            "--repo",
            str(FIXTURE),
            "--workspace",
            str(workspace),
            "--app-folder",
            app_folder,
        ],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    requirement_file = out / name / "requirement.md"
    requirement_file.write_text(task["requirement"], encoding="utf-8")
    try:
        run = subprocess.run(
            [
                str(FORGE),
                "run",
                "--workspace",
                str(workspace),
                "--requirement-file",
                str(requirement_file),
                "--auto-approve",
                "--output-format",
                "json",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_S,
        )
        exit_code, stdout = run.returncode, run.stdout
    except subprocess.TimeoutExpired:
        exit_code, stdout = -1, ""
    (out / name / "forge_run.json").write_text(stdout, encoding="utf-8")
    try:
        result = json.loads(stdout[stdout.index("{") :]) if "{" in stdout else {}
    except json.JSONDecodeError:
        result = {}

    app_dir = workspace / "repo" / app_folder
    hidden = app_dir / "tests" / "test_hidden_acceptance.py"
    shutil.copyfile(TASKS / name / "hidden_test.py", hidden)
    hidden_run = _pytest(app_dir, [str(hidden.relative_to(app_dir))])
    full_run = _pytest(app_dir, [])
    (out / name / "hidden_pytest.txt").write_text(hidden_run.stdout + hidden_run.stderr, encoding="utf-8")
    (out / name / "full_pytest.txt").write_text(full_run.stdout + full_run.stderr, encoding="utf-8")
    return {
        "task": name,
        "forge_exit": exit_code,
        "phase": result.get("phase", "?"),
        "hidden_pass": hidden_run.returncode == 0,
        "suite_pass": full_run.returncode == 0,
        "suite_summary": (full_run.stdout.strip().splitlines() or ["?"])[-1],
        "minutes": round((time.monotonic() - started) / 60, 1),
    }


def _pytest(app_dir: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(FIXTURE_PYTHON), "-m", "pytest", "-q", "-p", "no:cacheprovider", *args],
        cwd=app_dir,
        capture_output=True,
        text=True,
        timeout=600,
        env={**os.environ, "PYTHONPATH": str(app_dir)},
    )


def main(argv: list[str]) -> int:
    names = argv or sorted(p.name for p in TASKS.iterdir() if (p / "task.yaml").exists())
    out = REPO_ROOT / "test-artifacts" / f"evals-{time.strftime('%Y%m%d-%H%M%S')}"
    out.mkdir(parents=True)
    rows = []
    for name in names:
        print(f"== {name}", flush=True)
        row = run_task(name, out)
        print(json.dumps(row), flush=True)
        rows.append(row)
    lines = [
        "# Fixture evals",
        "",
        "| task | forge exit | phase | hidden test | full suite | minutes |",
        "|---|---|---|---|---|---|",
        *[
            f"| {r['task']} | {r['forge_exit']} | {r['phase']} | {'PASS' if r['hidden_pass'] else 'FAIL'} | "
            f"{'PASS' if r['suite_pass'] else 'FAIL'} ({r['suite_summary']}) | {r['minutes']} |"
            for r in rows
        ],
        "",
        f"Hidden tests passed: {sum(bool(r['hidden_pass']) for r in rows)}/{len(rows)}; "
        f"full suite green: {sum(bool(r['suite_pass']) for r in rows)}/{len(rows)}.",
    ]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if all(r["hidden_pass"] and r["suite_pass"] for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
