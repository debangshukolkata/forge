"""Rubric judge for the coding benchmark (TODO C1). Reads a run folder written by run_code_benchmark.py, shows the judge model
each task's prompt, the files DebCraft delivered (size-capped) and the rubric, and writes judge.json and judge.md next to results.json.
It calls the configured `judge` model role, so it spends tokens: run it by hand, never from the test suite.

    python scripts/benchmark/judge_code.py <run-name-or-folder> [--tasks t01_slugify,t15_rest_inventory_api] [--parallel 3] [--model gpt54]

Run folder layout (from run_code_benchmark.py): <run>/<task id>/project/ (and output/) hold the delivered files, <run>/results.json the scores.
The judge sees the code, not the hidden tests, so its scores are an independent second opinion next to the hidden-test pass rate.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_code_benchmark import REPO, RUNS, SKIPPED, TASKS

CRITERIA = ("correctness", "edge_cases", "error_handling", "tests", "security", "simplicity", "readability")
RUBRIC = """You are a strict senior engineer reviewing code that an AI coding agent delivered for one task. You see the task text,
the files that were delivered (new or changed files in full, unchanged starting files by name only) and nothing else: you cannot run the code.
Judge what is on the page. Use the whole scale; do not reward length or confidence.

Score each criterion from 0 to 5 (integers) with a one-line reason that names a concrete thing in the code:
- correctness: does the code do what the task text says, including every stated rule and exact format? 5 = nothing you can find is wrong, 3 = works for the main cases but misses a stated rule, 0 = broken or missing.
- edge_cases: boundaries, empty and odd inputs, ordering, rounding, repeated runs, the unusual cases the task text hints at.
- error_handling: the right exceptions, messages and exit codes as asked; no silent failures, no bare except, nothing half done on failure.
- tests: the agent's own tests: do they prove behaviour (assertions on results, edge cases, failure cases) or only run the code? If the task asked for tests and there are none, give 0; if the task asked for none, judge any that exist.
- security: injection, path traversal, unsafe deserialisation or eval, secrets, unsafe file or shell use, trusting input. 5 = nothing risky; if the task has no security surface, give 5 unless the code adds a risk.
- simplicity: no needless abstraction, dead code or over-engineering; the smallest design that meets the task; existing code style kept in an existing repository.
- readability: names, structure, comments that explain why, small functions, consistent formatting.

Also give "overall" (0 to 5, your judgement, not an average), "summary" (two sentences) and "worst_problem" (the single most important defect, or "none").
Reply with one JSON object only, no markdown fence, in exactly this shape:
{"correctness": {"score": n, "reason": "..."}, "edge_cases": {...}, "error_handling": {...}, "tests": {...}, "security": {...}, "simplicity": {...}, "readability": {...}, "overall": n, "summary": "...", "worst_problem": "..."}"""

MAX_FILE_CHARS = 14_000
MAX_TOTAL_CHARS = 60_000
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".cfg",
    ".ini",
    ".yaml",
    ".yml",
    ".csv",
    ".sh",
    ".html",
    ".js",
    ".ts",
}


def delivered_files(workspace: Path, seed: Path) -> tuple[list[tuple[str, str]], list[str], list[str]]:
    """(changed or new files with their text, unchanged seed file names, names left out for size or type)."""
    changed: list[tuple[str, str]] = []
    unchanged: list[str] = []
    left_out: list[str] = []
    seen: set[str] = set()
    for folder in ("project", "output"):
        root = workspace / folder
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if not path.is_file() or SKIPPED.intersection(relative.parts) or path.suffix.lower() == ".pyc":
                continue
            name = relative.as_posix() if folder == "project" else f"output/{relative.as_posix()}"
            if name in seen:
                continue
            seen.add(name)
            if path.suffix.lower() not in TEXT_SUFFIXES:
                left_out.append(f"{name} (not a text file)")
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                left_out.append(f"{name} (unreadable)")
                continue
            seed_file = seed / relative
            if folder == "project" and seed_file.is_file() and _same(seed_file, text):
                unchanged.append(name)
                continue
            changed.append((name, text))
    return changed, unchanged, left_out


def _same(seed_file: Path, text: str) -> bool:
    try:
        return seed_file.read_text(encoding="utf-8").replace("\r\n", "\n") == text.replace("\r\n", "\n")
    except (OSError, UnicodeDecodeError):
        return False


def render_files(changed: list[tuple[str, str]], unchanged: list[str], left_out: list[str]) -> str:
    """Tests and the biggest files are shortened first so that every file shows at least its start."""
    budget = MAX_TOTAL_CHARS
    parts: list[str] = []
    for name, text in sorted(
        changed, key=lambda item: (len(item[1]), item[0])
    ):  # small files first, so they are never cut
        allowed = max(min(MAX_FILE_CHARS, budget), 500)
        shown = (
            text
            if len(text) <= allowed
            else text[:allowed] + f"\n... [cut: {len(text) - allowed} more characters]"
        )
        budget -= len(shown)
        parts.append(f"=== FILE {name} ({len(text)} characters) ===\n{shown}")
    if unchanged:
        parts.append("=== UNCHANGED STARTING FILES (not shown) ===\n" + "\n".join(unchanged))
    if left_out:
        parts.append("=== OTHER FILES NOT SHOWN ===\n" + "\n".join(left_out))
    return "\n\n".join(parts) if parts else "(no files were delivered)"


def build_prompt(task_text: str, files_text: str, hidden: dict[str, Any]) -> str:
    score_line = ""
    if hidden.get("hidden_total"):
        score_line = (
            f"\nFor context only: the benchmark's hidden tests passed {hidden.get('hidden_passed')} of {hidden.get('hidden_total')}. "
            "Do not simply copy that into your scores; judge the code."
        )
    return f"TASK GIVEN TO THE AGENT\n{task_text.strip()}\n\nDELIVERED CODE\n{files_text}\n{score_line}\n\nNow score it with the rubric."


def parse_scores(text: str) -> dict[str, Any]:
    found = re.search(r"\{.*\}", text, re.S)
    if not found:
        return {"error": f"no JSON in the reply: {text[:200]}"}
    try:
        data = json.loads(found.group(0))
    except ValueError as error:
        return {"error": f"bad JSON ({error}): {text[:200]}"}
    problems = []
    for criterion in CRITERIA:
        entry = data.get(criterion)
        score = entry.get("score") if isinstance(entry, dict) else None
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 5:
            problems.append(criterion)
        elif isinstance(entry, dict):
            entry["score"] = round(score)
    overall = data.get("overall")
    if isinstance(overall, bool) or not isinstance(overall, (int, float)) or not 0 <= overall <= 5:
        problems.append("overall")
    if problems:
        data["error"] = "missing or out-of-range scores: " + ", ".join(problems)
    return data  # type: ignore[no-any-return]


async def ask_judge(router: Any, prompt: str) -> str:
    from forge.llm.base import ChatRequest, Message

    response = await router.chat(
        "judge", ChatRequest(messages=[Message.system(RUBRIC), Message(role="user", content=prompt)])
    )
    return str(response.text)


async def judge_task(router: Any, run_dir: Path, task_id: str, hidden: dict[str, Any]) -> dict[str, Any]:
    task = TASKS / task_id
    workspace = run_dir / task_id
    if not (task / "task.md").exists():
        return {"id": task_id, "error": "task folder not found in tests/benchmarks/tasks"}
    changed, unchanged, left_out = delivered_files(workspace, task / "seed")
    if not changed:
        return {"id": task_id, "error": "nothing delivered", "overall": 0}
    prompt = build_prompt(
        (task / "task.md").read_text(encoding="utf-8"), render_files(changed, unchanged, left_out), hidden
    )
    try:
        reply = await ask_judge(router, prompt)
    except Exception as error:
        return {"id": task_id, "error": f"{type(error).__name__}: {str(error)[:200]}"}
    scores = parse_scores(reply)
    scores["id"] = task_id
    scores["files_judged"] = [name for name, _ in changed]
    return scores


def markdown(name: str, rows: list[dict[str, Any]], results: dict[str, dict[str, Any]]) -> str:
    head = " | ".join(c.replace("_", " ") for c in CRITERIA)
    lines = [
        f"### Judge for run `{name}` ({datetime.now():%Y-%m-%d %H:%M})",
        "",
        f"| Task | Hidden tests | {head} | Overall |",
        "|---|---|" + "---|" * len(CRITERIA) + "---|",
    ]
    totals = {c: [] for c in CRITERIA}  # type: dict[str, list[int]]
    overalls: list[float] = []
    for row in rows:
        hidden = results.get(row["id"], {})
        tests = f"{hidden.get('hidden_passed', '?')}/{hidden.get('hidden_total', '?')}"
        if "error" in row and not all(isinstance(row.get(c), dict) for c in CRITERIA):
            lines.append(f"| {row['id']} | {tests} | JUDGE ERROR: {row['error']} |" + " |" * len(CRITERIA))
            continue
        cells = []
        for criterion in CRITERIA:
            score = row[criterion]["score"]
            totals[criterion].append(score)
            cells.append(str(score))
        overalls.append(float(row["overall"]))
        lines.append(f"| {row['id']} | {tests} | " + " | ".join(cells) + f" | {row['overall']} |")
    if overalls:
        means = " | ".join(f"{sum(v) / len(v):.1f}" for v in totals.values())
        lines.append(f"| **mean** | | {means} | {sum(overalls) / len(overalls):.1f} |")
    lines += [
        "",
        "Scores are 0 to 5; the judge model sees the delivered code and the task text, not the hidden tests.",
        "",
    ]
    for row in rows:
        if "summary" in row or "worst_problem" in row:
            lines.append(
                f"**{row['id']}**: {row.get('summary', '')} Worst problem: {row.get('worst_problem', 'n/a')}"
            )
            for criterion in CRITERIA:
                entry = row.get(criterion)
                if isinstance(entry, dict):
                    lines.append(
                        f"- {criterion.replace('_', ' ')} {entry.get('score')}: {entry.get('reason', '')}"
                    )
            lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", help="a run name under the codebench folder, or the path of a run folder")
    parser.add_argument(
        "--tasks", default="", help="comma-separated task ids (default: every task in results.json)"
    )
    parser.add_argument("--parallel", type=int, default=1, help="judge calls at the same time")
    parser.add_argument(
        "--model", default="", help="a model key (for example gpt54) to use for the judge role"
    )
    args = parser.parse_args()
    run_dir = Path(args.run) if Path(args.run).is_dir() else RUNS / args.run
    results_file = run_dir / "results.json"
    if not results_file.exists():
        print(f"no results.json in {run_dir}", file=sys.stderr)
        return 1
    results = {row["id"]: row for row in json.loads(results_file.read_text(encoding="utf-8"))}
    wanted = [t for t in args.tasks.split(",") if t] or list(results)

    home = run_dir / "judge_home"
    home.mkdir(exist_ok=True)
    os.environ.setdefault("FORGE_ENV_FILE", str(REPO / ".env"))
    os.environ["FORGE_HOME"] = str(
        home
    )  # an own home: the judge never reads or writes a DebCraft project's files
    if args.model:
        import yaml

        (home / "config.yaml").write_text(
            yaml.safe_dump({"llm": {"roles": {"judge": args.model}}}), encoding="utf-8"
        )
    sys.path.insert(0, str(REPO))
    from forge.config import load_config, load_secrets
    from tests.test_live_llm import router_for

    router = router_for(load_config(), load_secrets())

    async def run_all() -> list[dict[str, Any]]:
        # one event loop for all calls: the router's HTTP clients belong to the loop they were first used in
        gate = asyncio.Semaphore(max(args.parallel, 1))

        async def one(task_id: str) -> dict[str, Any]:
            async with gate:
                print(f"[judge] {task_id} ...", flush=True)
                row = await judge_task(router, run_dir, task_id, results.get(task_id, {}))
                print(f"[judge] {task_id}: overall {row.get('overall', row.get('error'))}", flush=True)
                return row

        return list(await asyncio.gather(*(one(t) for t in wanted)))

    rows = asyncio.run(run_all())
    (run_dir / "judge.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    report = markdown(run_dir.name, rows, results)
    (run_dir / "judge.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
