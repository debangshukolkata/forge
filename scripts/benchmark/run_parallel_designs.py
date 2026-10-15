"""Serial against parallel designs (TODO X8, D-362): the same brief for three throwaway designs, built with builders one at a time
(limits.max_parallel_builders 1) or three at a time (3).

    python scripts/benchmark/run_parallel_designs.py <run-name> [--runs 3] [--env KEY=VALUE ...]

Arms alternate (serial, parallel, serial, ...) so quota and machine drift hit both. Each run gets its own FORGE_HOME with the arm's config.
Results go to C:\\Work\\ForgeRuns\\paralleldesigns\\<run-name> and a table is printed for docs/SPEED_BENCHMARK.md. It spends Azure tokens
(about $2 to $4 a run), so run it by hand and never beside another timing run."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_code_benchmark import PYTHON, REPO
from run_speed_benchmark import _seconds, timing

sys.path.insert(0, str(Path(__file__).resolve().parent))
from awake import keep_awake, stall_note

BRIEF = REPO / "tests" / "benchmarks" / "parallel" / "three_designs.md"
RUNS = Path(os.environ.get("FORGE_BENCH_RUNS", r"C:\Work\ForgeRuns")) / "paralleldesigns"
ARMS = {"serial": 1, "parallel": 3}


def read_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def concurrency(events_path: Path) -> dict[str, object]:
    """How many helper agents ran at the same time, how many were started, and whether the network pushed back (429)."""
    events = read_events(events_path)
    points: list[tuple[float, int]] = []
    roles: list[str] = []
    for e in events:
        if e["type"] == "agent_started":
            points.append((_seconds(str(e["ts"])), 1))
            roles.append(str(e["payload"].get("role")))  # type: ignore[union-attr]
        elif e["type"] == "agent_finished":
            points.append((_seconds(str(e["ts"])), -1))
    running = peak = 0
    for _, delta in sorted(points):
        running += delta
        peak = max(peak, running)
    retries = sum(1 for e in events if e["type"] == "notice" and "429" in json.dumps(e["payload"]))
    return {"agents": len(roles), "peak_agents": peak, "notices_429": retries}


def check_designs(workspace: Path) -> dict[str, object]:
    from playwright.sync_api import sync_playwright

    from forge.tools.ui_audit import AUDIT_SCRIPT

    pages = sorted((workspace / "project").glob("designs/*/index.html")) or sorted(
        (workspace / "designs").glob("*/index.html")
    )
    findings = 0
    sideways = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        for page_file in pages:
            for width in (1280, 375):
                page = browser.new_page(viewport={"width": width, "height": 800})
                page.goto(page_file.resolve().as_uri())
                page.wait_for_timeout(400)
                if page.evaluate("document.documentElement.scrollWidth - window.innerWidth") > 1:
                    sideways += 1
                if width == 1280:
                    findings += len(page.evaluate(AUDIT_SCRIPT).get("findings", []))
                page.close()
        browser.close()
    sheets = [f.parent / "style.css" for f in pages]
    sources = {s.read_text(encoding="utf-8", errors="replace")[:3000] for s in sheets if s.is_file()}
    return {
        "designs": len(pages),
        "audit_findings": findings,
        "sideways_scroll_pages": sideways,
        "distinct_sources": len(sources),
    }


def one_run(name: str, arm: str, index: int, env: dict[str, str]) -> dict[str, object]:
    import yaml

    run_dir = RUNS / name / f"{arm}-{index}"
    shutil.rmtree(run_dir, ignore_errors=True)
    home = run_dir / "home"
    home.mkdir(parents=True)
    (home / "config.yaml").write_text(
        yaml.safe_dump({"limits": {"max_parallel_builders": ARMS[arm]}}), encoding="utf-8"
    )
    run_env = {**env, "FORGE_HOME": str(home)}
    workspace = run_dir / "ws"
    created = subprocess.run(
        [
            str(PYTHON),
            "-m",
            "forge.cli",
            "new",
            "--standalone",
            "--project",
            f"par-{arm}-{index}",
            "--workspace",
            str(workspace),
        ],
        env=run_env,
        capture_output=True,
        text=True,
    )
    if created.returncode != 0:
        return {"arm": arm, "run": index, "error": created.stdout[-300:] + created.stderr[-300:]}
    started = time.time()
    try:
        subprocess.run(
            [
                str(PYTHON),
                str(REPO / "scripts" / "campaign" / "drive_forge.py"),
                str(workspace),
                str(BRIEF),
                str(run_dir / "run.json"),
            ],
            env=run_env,
            capture_output=True,
            timeout=5400,
        )
        timed_out = False
    except subprocess.TimeoutExpired:
        timed_out = True
    events = workspace / ".forge" / "transcripts" / "events.jsonl"
    row: dict[str, object] = {
        "arm": arm,
        "run": index,
        "outer_wall_s": round(time.time() - started),
        "timed_out": timed_out,
    }
    row.update(timing(events))
    row.update(concurrency(events))
    row.update(check_designs(workspace))
    (run_dir / "row.json").write_text(json.dumps(row, indent=1, default=str), encoding="utf-8")
    return row


def markdown(name: str, rows: list[dict[str, object]]) -> str:
    lines = [
        f"### Run `{name}` ({time.strftime('%Y-%m-%d %H:%M')})",
        "",
        "| Arm | Run | Wall | Model calls | Input tokens | Cost | Agents (peak) | 429 notices | Designs | Audit left | Sideways | Distinct sheets |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['arm']} | {r['run']} | ERROR {r['error']} |" + " |" * 9)
            continue
        lines.append(
            f"| {r['arm']} | {r['run']} | {r.get('wall_s')} s{stall_note(r)} | {r.get('model_calls')} | {r.get('in_tokens')} | ${r.get('cost_usd')} | "
            f"{r.get('agents')} ({r.get('peak_agents')}) | {r.get('notices_429')} | {r.get('designs')} | {r.get('audit_findings')} | "
            f"{r.get('sideways_scroll_pages')} | {r.get('distinct_sources')} |"
        )
    for arm in ARMS:
        walls = [int(str(r["wall_s"])) for r in rows if r["arm"] == arm and r.get("wall_s")]
        if walls:
            lines.append(
                f"\n{arm}: mean wall {sum(walls) / len(walls):.0f} s over {len(walls)} runs ({', '.join(str(w) for w in walls)})"
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--env", action="append", default=[])
    args = parser.parse_args()
    keep_awake()
    env = {**os.environ, "FORGE_ENV_FILE": str(REPO / ".env"), "PYTHONIOENCODING": "utf-8"}
    for pair in args.env:
        key, _, value = pair.partition("=")
        env[key] = value
    rows: list[dict[str, object]] = []
    out = RUNS / args.name
    out.mkdir(parents=True, exist_ok=True)
    for index in range(1, args.runs + 1):
        for arm in ARMS:
            print(f"[{args.name}] {arm} {index} ...", flush=True)
            rows.append(one_run(args.name, arm, index, env))
            (out / "results.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    report = markdown(args.name, rows)
    (out / "results.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
