"""Coding benchmark runner (TODO C1). Runs DebCraft on each task in tests/benchmarks/tasks on the real model, then scores
the result with the hidden tests. This spends Azure tokens, so it is run by hand, never by the test suite.

    python scripts/benchmark/run_code_benchmark.py <run-name> [--tasks t01_slugify,t04_paginate_bug] [--env KEY=VALUE ...]

Everything lives under C:\\Work\\ForgeRuns\\codebench\\<run-name> (one workspace per task, an isolated DebCraft home).
Results go to results.json and a markdown table is printed; paste the table into docs/CODE_BENCHMARK.md with the
date and what changed. Scoring per task: hidden-test pass rate, wall time, model calls, tokens and cost. The judge
rubric score (correctness, edge cases, error handling, tests, security, simplicity, readability) is still a manual
step: read the delivered code and score it 1-5 per line.

Mode B layout: seed files are put in <workspace>/project (the user's pasted code); the finished code is read from
there or from output/. The model may install packages with pip into the workspace's own environment (approved by
drive_forge.py).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TASKS = REPO / "tests" / "benchmarks" / "tasks"
RUNS = Path(os.environ.get("FORGE_BENCH_RUNS", r"C:\Work\ForgeRuns")) / "codebench"
PYTHON = REPO / ".venv" / "Scripts" / "python.exe"
SKIPPED = {".venv", ".forge", "node_modules", "__pycache__", ".pytest_cache", "_harness"}
HIDDEN_LIMIT_S = 300


def find_entry(workspace: Path, entry: str) -> Path | None:
    """The delivered module: under project/ first, then output/."""
    for folder in ("project", "output"):
        for path in sorted((workspace / folder).rglob(entry)):
            if not SKIPPED.intersection(path.relative_to(workspace / folder).parts):
                return path
    return None


def score(
    workspace: Path, task: Path, entry: str, scratch: Path, python: Path | None = None
) -> dict[str, object]:
    found = find_entry(workspace, entry)
    if found is None:
        return {
            "delivered": False,
            "hidden_passed": 0,
            "hidden_failed": 0,
            "hidden_total": 0,
            "note": f"{entry} not found",
        }
    shutil.rmtree(scratch, ignore_errors=True)
    shutil.copytree(
        found.parent,
        scratch,
        ignore=shutil.ignore_patterns(*SKIPPED, "test_*.py", "*_test.py", "conftest.py"),
    )  # the model's own tests are left out so they cannot shadow or break the hidden ones
    shutil.copytree(task / "hidden", scratch / "hidden_tests")
    run = subprocess.run(
        [
            str(python or workspace / ".venv" / "Scripts" / "python.exe"),
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "hidden_tests",
        ],
        cwd=scratch,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=HIDDEN_LIMIT_S,
        env={**os.environ, "PYTHONPATH": str(scratch), "PYTHONIOENCODING": "utf-8"},
    )
    passed = int((re.search(r"(\d+) passed", run.stdout) or [0, 0])[1])
    failed = int((re.search(r"(\d+) failed", run.stdout) or [0, 0])[1]) + int(
        (re.search(r"(\d+) error", run.stdout) or [0, 0])[1]
    )
    return {
        "delivered": True,
        "hidden_passed": passed,
        "hidden_failed": failed,
        "hidden_total": passed + failed,
        "tail": run.stdout.strip().splitlines()[-3:],
    }


def event_numbers(events_path: Path) -> dict[str, object]:
    if not events_path.exists():
        return {}
    events = [
        json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    llm = [e["payload"] for e in events if e["type"] == "llm_call"]
    tools = [e["payload"] for e in events if e["type"] == "tool_call_finished"]
    costs = [e["payload"] for e in events if e["type"] == "cost_updated"]
    return {
        "model_calls": len(llm),
        "model_s": round(sum(c.get("latency_s", 0.0) for c in llm)),
        "tool_calls": len(tools),
        "tool_s": round(sum(t.get("duration_s", 0.0) for t in tools)),
        "waited_s": round(sum(t.get("waited_s", 0.0) for t in tools)),
        "in_tokens": sum(c["usage"].get("input_tokens", 0) for c in llm),
        "out_tokens": sum(c["usage"].get("output_tokens", 0) for c in llm),
        "cost_usd": costs[-1].get("total_usd") if costs else None,
    }


def run_task(task: Path, run_dir: Path, env: dict[str, str]) -> dict[str, object]:
    meta = json.loads((task / "task.json").read_text(encoding="utf-8"))
    workspace = run_dir / meta["id"]
    shutil.rmtree(workspace, ignore_errors=True)
    created = subprocess.run(
        [
            str(PYTHON),
            "-m",
            "forge.cli",
            "new",
            "--standalone",
            "--project",
            f"bench-{meta['id']}",
            "--workspace",
            str(workspace),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    if created.returncode != 0:
        return {
            "id": meta["id"],
            "tier": meta["tier"],
            "error": f"workspace setup failed: {created.stdout[-300:]}{created.stderr[-300:]}",
        }
    if (task / "seed").exists():
        shutil.copytree(task / "seed", workspace / "project", dirs_exist_ok=True)
    prompt = (task / "task.md").read_text(encoding="utf-8") + (
        "\n\nYou may install packages with `python -m pip install ...` in this project's environment: that is approved."
    )
    prompt_file = run_dir / f"{meta['id']}_prompt.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    result_file = run_dir / f"{meta['id']}_run.json"
    started = time.time()
    try:
        subprocess.run(
            [
                str(PYTHON),
                str(REPO / "scripts" / "campaign" / "drive_forge.py"),
                str(workspace),
                str(prompt_file),
                str(result_file),
            ],
            env=env,
            capture_output=True,
            timeout=3600,
        )
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
    wall = round(time.time() - started)
    row: dict[str, object] = {"id": meta["id"], "tier": meta["tier"], "wall_s": wall, "timed_out": timed_out}
    row.update(event_numbers(workspace / ".forge" / "transcripts" / "events.jsonl"))
    row.update(score(workspace, task, meta["entry"], run_dir / f"{meta['id']}_scoring"))
    return row


def markdown(name: str, rows: list[dict[str, object]]) -> str:
    lines = [
        f"### Run `{name}` ({datetime.now():%Y-%m-%d %H:%M})",
        "",
        "| Task | Tier | Hidden tests | Wall | Model calls | Tool s | Waited s | Tokens in/out | Cost |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        if "error" in row:
            lines.append(f"| {row['id']} | {row['tier']} | ERROR: {row['error']} | | | | | | |")
            continue
        cost = row.get("cost_usd")
        lines.append(
            f"| {row['id']} | {row['tier']} | {row.get('hidden_passed', 0)}/{row.get('hidden_total', 0)}"
            f"{'' if row.get('delivered') else ' (not delivered)'} | {row['wall_s']}s | {row.get('model_calls', '?')} | "
            f"{row.get('tool_s', '?')} | {row.get('waited_s', '?')} | {row.get('in_tokens', '?')}/{row.get('out_tokens', '?')} | "
            f"{'' if cost is None else f'${float(cost):.3f}'} |"
        )
    total = sum(int(r.get("hidden_passed", 0)) for r in rows)
    count = sum(int(r.get("hidden_total", 0)) for r in rows)
    solved = sum(1 for r in rows if r.get("hidden_total") and r.get("hidden_failed") == 0)
    lines += ["", f"Tasks fully passed: {solved}/{len(rows)}; hidden tests passed: {total}/{count}."]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--tasks", default="", help="comma-separated task ids (default: all)")
    parser.add_argument("--env", action="append", default=[], help="KEY=VALUE for the DebCraft process")
    args = parser.parse_args()
    run_dir = RUNS / args.name
    run_dir.mkdir(parents=True, exist_ok=True)
    home = run_dir / "home"
    home.mkdir(exist_ok=True)
    env = {
        **os.environ,
        "FORGE_HOME": str(home),
        "FORGE_ENV_FILE": str(REPO / ".env"),
        "PYTHONIOENCODING": "utf-8",
    }
    for pair in args.env:
        key, _, value = pair.partition("=")
        env[key] = value
    wanted = {t for t in args.tasks.split(",") if t}
    folders = [p for p in sorted(TASKS.iterdir()) if p.is_dir() and (not wanted or p.name in wanted)]
    rows: list[dict[str, object]] = []
    for task in folders:
        print(f"[{args.name}] {task.name} ...", flush=True)
        rows.append(run_task(task, run_dir, env))
        (run_dir / "results.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
        print(
            f"[{args.name}] {task.name}: {rows[-1].get('hidden_passed')}/{rows[-1].get('hidden_total')} in {rows[-1].get('wall_s')}s",
            flush=True,
        )
    report = markdown(args.name, rows)
    (run_dir / "results.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
