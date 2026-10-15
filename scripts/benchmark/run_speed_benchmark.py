"""Speed benchmark (TODO S2). A few fixed tasks, each timed in detail and checked for quality, run on the real model before and after
every speed change. A speed change that lowers the quality score is rejected (D-161: accuracy and speed come before cost).

    python scripts/benchmark/run_speed_benchmark.py <run-name> [--tasks s01_crud_api,s03_page_redesign] [--env KEY=VALUE ...]
    python scripts/benchmark/run_speed_benchmark.py --compare <before-run> <after-run>

Tasks live in tests/benchmarks/speed. Each run reports where the time went: model calls, tools (by name, with the slowest
commands), waiting for the user, and the rest (engine and parallel overlap), plus the quality check (hidden tests, or for a page a
browser check at desktop and phone width). Results are under C:\\Work\\ForgeRuns\\speedbench\\<run-name>; paste the table into
docs/SPEED_BENCHMARK.md with the date and what changed. This spends Azure tokens, so it is run by hand."""

from __future__ import annotations

import argparse
import itertools
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_code_benchmark import PYTHON, REPO, score

sys.path.insert(0, str(Path(__file__).resolve().parent))
from awake import keep_awake

TASKS = REPO / "tests" / "benchmarks" / "speed"
RUNS = Path(os.environ.get("FORGE_BENCH_RUNS", r"C:\Work\ForgeRuns")) / "speedbench"
PAGE_PHRASES = [
    "sunrise bakery", "6am", "sourdough", "6.50", "croissant", "3.20", "cinnamon", "3.80", "rye", "5.90", "baguette", "2.80",
    "1987", "mill lane", "555-0142", "hello@sunrisebakery.example", "monday", "cake",
]  # fmt: skip
DEPRECATED_TAGS = ("marquee", "blink", "font", "center")


# --- timing from the event log ---


STALL_LIMIT_S = 900.0  # no event and no model answer for 15 minutes: the machine slept or lost its network, the timing of that run says nothing (seen live 2026-10-15: one call took 6,700 s)


def _seconds(stamp: str) -> float:
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()


def timing(events_path: Path) -> dict[str, object]:
    """Where the time went, from the transcript events."""
    if not events_path.exists():
        return {}
    events = [
        json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if not events:
        return {}
    stamps = [_seconds(e["ts"]) for e in events]
    wall = stamps[-1] - stamps[0]
    model = [e for e in events if e["type"] == "llm_call"]
    tools = [e["payload"] for e in events if e["type"] == "tool_call_finished"]
    started = {e["payload"]["id"]: _seconds(e["ts"]) for e in events if e["type"] == "tool_call_started"}
    first_tool = next((started[i] - stamps[0] for i in started), None)
    model_s = sum(e["payload"].get("latency_s", 0.0) for e in model)
    waited = sum(t.get("waited_s", 0.0) for t in tools)
    tool_s = sum(t.get("duration_s", 0.0) for t in tools) - waited
    by_tool: dict[str, float] = {}
    for t in tools:
        by_tool[t["name"]] = by_tool.get(t["name"], 0.0) + t.get("duration_s", 0.0) - t.get("waited_s", 0.0)
    slowest = sorted(tools, key=lambda t: t.get("duration_s", 0.0) - t.get("waited_s", 0.0), reverse=True)[:3]
    costs = [e["payload"] for e in events if e["type"] == "cost_updated"]
    longest_gap = max((b - a for a, b in itertools.pairwise(stamps)), default=0.0)
    longest_call = max((e["payload"].get("latency_s", 0.0) for e in model), default=0.0)
    stalled = max(longest_gap, longest_call)
    return {
        "timing_valid": stalled < STALL_LIMIT_S,
        "longest_gap_s": round(longest_gap),
        "longest_model_call_s": round(longest_call),
        "wall_s": round(wall),
        "model_s": round(model_s),
        "tool_s": round(tool_s),
        "waited_s": round(waited),
        "other_s": round(
            wall - model_s - tool_s - waited
        ),  # engine work, and model/tool time that overlapped
        "model_calls": len(model),
        "tool_calls": len(tools),
        "first_tool_s": None if first_tool is None else round(first_tool),
        "by_tool_s": {k: round(v) for k, v in sorted(by_tool.items(), key=lambda kv: -kv[1])[:5] if v >= 1},
        "slowest": [
            f"{t['name']} {t.get('duration_s', 0):.0f}s: {str(t.get('summary', ''))[:60]}" for t in slowest
        ],
        "in_tokens": sum(e["payload"]["usage"].get("input_tokens", 0) for e in model),
        "cost_usd": costs[-1].get("total_usd") if costs else None,
    }


# --- quality checks ---


def check_page(workspace: Path) -> dict[str, object]:
    """The redesigned page in headless Edge at desktop and phone width: seven checks."""
    page_file = next(iter(sorted((workspace / "project").rglob("index.html"))), None)
    if page_file is None:
        return {"delivered": False, "hidden_passed": 0, "hidden_total": 8, "hidden_failed": 8}
    from playwright.sync_api import sync_playwright

    html = page_file.read_text(encoding="utf-8", errors="replace")
    lowered = html.lower()
    passed: dict[str, bool] = {}
    problems: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        for name, width in (("desktop", 1280), ("phone", 375)):
            page = browser.new_page(viewport={"width": width, "height": 800})
            errors: list[str] = []
            page.on("console", lambda m, errors=errors: errors.append(m.text) if m.type == "error" else None)
            page.goto(page_file.resolve().as_uri())
            page.wait_for_timeout(300)
            wide = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
            passed[f"no sideways scroll at {name}"] = wide <= 1
            if name == "desktop":
                text = page.evaluate("document.body.innerText").lower()
                broken = page.evaluate("[...document.images].filter(i => !i.naturalWidth).length")
                passed["no broken images"] = broken == 0
                passed["no console errors"] = not [e for e in errors if "favicon" not in e]
            page.close()
        browser.close()
    passed["all information kept"] = all(
        phrase in text.replace(" ", "") or phrase in text for phrase in PAGE_PHRASES
    )
    passed["viewport meta and lang"] = 'name="viewport"' in lowered.replace("'", '"') and " lang=" in lowered
    passed["no obsolete tags, one h1"] = (
        not any(f"<{t}" in lowered for t in DEPRECATED_TAGS) and lowered.count("<h1") == 1
    )
    problems = [name for name, ok in passed.items() if not ok]
    total = len(passed)
    return {
        "delivered": True,
        "hidden_passed": total - len(problems),
        "hidden_total": total,
        "hidden_failed": len(problems),
        "tail": problems,
    }


# --- running ---


def run_task(task: Path, run_dir: Path, env: dict[str, str]) -> dict[str, object]:
    meta = json.loads((task / "task.json").read_text(encoding="utf-8"))
    workspace = run_dir / meta["id"]
    shutil.rmtree(workspace, ignore_errors=True)
    created = subprocess.run(
        [str(PYTHON), "-m", "forge.cli", "new", "--standalone", "--project", f"speed-{meta['id']}", "--workspace", str(workspace)],
        env=env, capture_output=True, text=True,
    )  # fmt: skip
    if created.returncode != 0:
        return {
            "id": meta["id"],
            "error": f"workspace setup failed: {created.stdout[-300:]}{created.stderr[-300:]}",
        }
    if (task / "seed").exists():
        shutil.copytree(task / "seed", workspace / "project", dirs_exist_ok=True)
    prompt = (task / "task.md").read_text(encoding="utf-8") + (
        "\n\nYou may install packages with `python -m pip install ...` in this project's environment: that is approved."
    )
    prompt_file = run_dir / f"{meta['id']}_prompt.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    started = time.time()
    try:
        subprocess.run(
            [str(PYTHON), str(REPO / "scripts" / "campaign" / "drive_forge.py"), str(workspace), str(prompt_file), str(run_dir / f"{meta['id']}_run.json")],
            env=env, capture_output=True, timeout=3600,
        )  # fmt: skip
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
    row: dict[str, object] = {
        "id": meta["id"],
        "title": meta["title"],
        "timed_out": timed_out,
        "outer_wall_s": round(time.time() - started),
    }
    row.update(timing(workspace / ".forge" / "transcripts" / "events.jsonl"))
    if meta["mode"] == "page":
        row.update(check_page(workspace))
    else:
        row.update(score(workspace, task, meta["entry"], run_dir / f"{meta['id']}_scoring"))
    return row


def markdown(name: str, rows: list[dict[str, object]]) -> str:
    lines = [
        f"### Run `{name}` ({datetime.now():%Y-%m-%d %H:%M})",
        "",
        "| Task | Quality | Wall | Model | Tools | Waited | Other | First tool | Calls | Tokens in | Cost |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['id']} | ERROR: {r['error']} |" + " |" * 9)
            continue
        cost = r.get("cost_usd")
        lines.append(
            f"| {r['id']} | {r.get('hidden_passed', 0)}/{r.get('hidden_total', 0)} | {r.get('wall_s')}s | {r.get('model_s')}s | "
            f"{r.get('tool_s')}s | {r.get('waited_s')}s | {r.get('other_s')}s | {r.get('first_tool_s')}s | "
            f"{r.get('model_calls')}+{r.get('tool_calls')} | {r.get('in_tokens')} | {'' if cost is None else f'${float(cost):.2f}'} |"  # type: ignore[arg-type]
        )
    lines.append("")
    for r in rows:
        if r.get("by_tool_s"):
            lines.append(
                f"- {r['id']}: tool time by tool {r['by_tool_s']}; slowest: {'; '.join(r.get('slowest', []))}"
            )  # type: ignore[arg-type]
    return "\n".join(lines)


def delta(a: dict[str, object], b: dict[str, object], key: str) -> str:
    x, y = a.get(key), b.get(key)
    return "-" if x is None or y is None else f"{x} -> {y}"


def compare(before: str, after: str) -> str:
    def load(name: str) -> dict[str, dict[str, object]]:
        return {r["id"]: r for r in json.loads((RUNS / name / "results.json").read_text(encoding="utf-8"))}

    old, new = load(before), load(after)
    lines = [
        f"### `{before}` -> `{after}`",
        "",
        "| Task | Quality | Wall | Model | Tools | Calls | Cost | Verdict |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for task_id in sorted(set(old) & set(new)):
        a, b = old[task_id], new[task_id]

        worse = (b.get("hidden_passed", 0) or 0) < (a.get("hidden_passed", 0) or 0)  # type: ignore[operator]
        faster = (b.get("wall_s") or 0) < (a.get("wall_s") or 0)  # type: ignore[operator]
        verdict = "REJECT: quality dropped" if worse else "faster" if faster else "not faster"
        lines.append(
            f"| {task_id} | {a.get('hidden_passed')}/{a.get('hidden_total')} -> {b.get('hidden_passed')}/{b.get('hidden_total')} | "
            f"{delta(a, b, 'wall_s')}s | {delta(a, b, 'model_s')}s | {delta(a, b, 'tool_s')}s | {delta(a, b, 'model_calls')} | {delta(a, b, 'cost_usd')} | {verdict} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name", nargs="?")
    parser.add_argument("--tasks", default="", help="comma-separated task ids (default: all)")
    parser.add_argument("--env", action="append", default=[], help="KEY=VALUE for the DebCraft process")
    parser.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    args = parser.parse_args()
    keep_awake()
    if args.compare:
        print(compare(*args.compare))
        return 0
    if not args.name:
        parser.error("give a run name")
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
    rows: list[dict[str, object]] = []
    for task in sorted(
        p for p in TASKS.iterdir() if (p / "task.json").exists() and (not wanted or p.name in wanted)
    ):
        print(f"[{args.name}] {task.name} ...", flush=True)
        rows.append(run_task(task, run_dir, env))
        (run_dir / "results.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
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
