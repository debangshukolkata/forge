"""Skill A/B loop (TODO C14, D-417): what is one skill worth?

    python scripts/benchmark/run_skill_ab.py <run-name> --skill test-first [--tasks t11_rate_limiter,t13_todo_undo] [--parallel 3] [--env KEY=VALUE ...]

Runs the coding benchmark twice on the same tasks, once as DebCraft ships (condition `with`) and once with the named skill switched off (condition `without`,
`FORGE_DISABLED_SKILLS=<skill>`: the skill is neither listed nor loadable), one after the other so that the two never compete for the machine, then prints one comparison:
tasks and hidden tests passed, model calls, wall time and cost, per task and in total. One run per condition is noisy: read a difference as a hint unless it is large, or repeat
with `--repeat 3`. Results: C:\\ForgeRuns\\codebench\\<run-name>-with and <run-name>-without, and the table is appended to docs/SKILL_AB.md with `--record`."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNS = Path(os.environ.get("FORGE_BENCH_RUNS", r"C:\Work\ForgeRuns")) / "codebench"
PYTHON = REPO / ".venv" / "Scripts" / "python.exe"
RECORD = REPO / "docs" / "SKILL_AB.md"


def run_condition(name: str, tasks: str, parallel: int, extra_env: list[str]) -> list[dict[str, object]]:
    command = [
        str(PYTHON if PYTHON.exists() else sys.executable),
        str(REPO / "scripts" / "benchmark" / "run_code_benchmark.py"),
        name,
        "--parallel",
        str(parallel),
    ]
    if tasks:
        command += ["--tasks", tasks]
    for pair in extra_env:
        command += ["--env", pair]
    subprocess.run(command, cwd=REPO, check=False)
    results = RUNS / name / "results.json"
    return json.loads(results.read_text(encoding="utf-8")) if results.exists() else []


def totals(rows: list[dict[str, object]]) -> dict[str, float]:
    return {
        "tasks": float(len(rows)),
        "tasks_passed": float(sum(1 for r in rows if r.get("hidden_total") and r.get("hidden_failed") == 0)),
        "tests_passed": float(sum(int(r.get("hidden_passed") or 0) for r in rows)),
        "tests_total": float(sum(int(r.get("hidden_total") or 0) for r in rows)),
        "calls": float(sum(int(r.get("model_calls") or 0) for r in rows)),
        "wall_s": float(sum(float(r.get("wall_s") or 0) for r in rows)),
        "cost_usd": float(sum(float(r.get("cost_usd") or 0) for r in rows)),
    }


def compare(skill: str, with_rows: list[dict[str, object]], without_rows: list[dict[str, object]]) -> str:
    """The comparison as markdown: a total line per condition and one row per task."""
    a, b = totals(with_rows), totals(without_rows)

    def line(label: str, t: dict[str, float]) -> str:
        return f"| {label} | {int(t['tasks_passed'])}/{int(t['tasks'])} | {int(t['tests_passed'])}/{int(t['tests_total'])} | {int(t['calls'])} | {t['wall_s']:.0f} | ${t['cost_usd']:.2f} |"

    lines = [
        f"### Skill `{skill}`: with and without",
        "",
        "| Condition | Tasks passed | Hidden tests | Model calls | Wall s | Cost |",
        "|---|---|---|---|---|---|",
        line("with the skill", a),
        line("without the skill", b),
        "",
        "| Task | with: tests / s / calls | without: tests / s / calls |",
        "|---|---|---|",
    ]
    without_by_task = {str(r.get("id")): r for r in without_rows}
    for row in with_rows:
        other = without_by_task.get(str(row.get("id")), {})

        def cell(r: dict[str, object]) -> str:
            return f"{r.get('hidden_passed', '-')}/{r.get('hidden_total', '-')} / {r.get('wall_s', '-')} / {r.get('model_calls', '-')}"

        lines.append(f"| {row.get('id')} | {cell(row)} | {cell(other)} |")
    delta_tests = a["tests_passed"] - b["tests_passed"]
    verdict = (
        "The skill helped: more hidden tests pass with it."
        if delta_tests > 0
        else "No difference in correctness."
        if delta_tests == 0
        else "The skill did not help: fewer hidden tests pass with it."
    )
    lines += [
        "",
        f"{verdict} Calls {int(a['calls'] - b['calls']):+d}, wall {a['wall_s'] - b['wall_s']:+.0f} s, cost {a['cost_usd'] - b['cost_usd']:+.2f} USD (with minus without).",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument(
        "--skill",
        required=True,
        help="the skill to switch off in the `without` condition, for example test-first",
    )
    parser.add_argument("--tasks", default="")
    parser.add_argument("--parallel", type=int, default=1)
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("--record", action="store_true", help="append the comparison to docs/SKILL_AB.md")
    args = parser.parse_args()
    with_rows = run_condition(f"{args.name}-with", args.tasks, args.parallel, args.env)
    without_rows = run_condition(
        f"{args.name}-without", args.tasks, args.parallel, [*args.env, f"FORGE_DISABLED_SKILLS={args.skill}"]
    )
    report = compare(args.skill, with_rows, without_rows)
    print(report)
    if args.record:
        RECORD.parent.mkdir(exist_ok=True)
        existing = (
            RECORD.read_text(encoding="utf-8") if RECORD.exists() else "# Skill A/B runs (C14, D-417)\n"
        )
        RECORD.write_text(existing.rstrip() + "\n\n" + report + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
