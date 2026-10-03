"""Speed/accuracy benchmark: the same three tasks (build the attendance app, leave-request enhancement, department
filter + CSV enhancement) run under one setting, each step checked by the independent Playwright script.

python bench.py <name> <port> [--env KEY=VALUE ...] [--config "yaml text"]

Everything lives under C:\\Work\\ForgeRuns (workspace bench_<name>, Forge home bench_<name>_home). Prints and writes
bench_<name>.json: per step wall time, model calls, model time, tokens, and the independent check result.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

RUNS = Path(r"C:\Work\ForgeRuns")
FORGE = Path(r"C:\Work\Projects\Forge")
PYTHON = FORGE / ".venv" / "Scripts" / "python.exe"
CAMPAIGN = FORGE / "scripts" / "campaign"
STEPS = [
    ("build", CAMPAIGN / "req_attendance.txt", 1),
    ("leave requests", CAMPAIGN / "enhancements" / "enh_attendance_1.txt", 2),
    ("department filter + CSV", CAMPAIGN / "enhancements" / "enh_attendance_2.txt", 3),
]


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("port")
    parser.add_argument("--env", action="append", default=[])
    parser.add_argument("--config", default="")
    return parser.parse_args()


def run_summary(events_path: Path, since_seq: int) -> dict[str, float]:
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    new = [e for e in events if e["seq"] > since_seq]
    llm = [e["payload"] for e in new if e["type"] == "llm_call"]
    tools = [e["payload"] for e in new if e["type"] == "tool_call_finished"]
    return {
        "last_seq": events[-1]["seq"] if events else since_seq,
        "model_calls": len(llm),
        "model_s": round(sum(c["latency_s"] for c in llm)),
        "tool_calls": len(tools),
        "tool_s": round(sum(t.get("duration_s", 0) for t in tools)),
        "in_tokens": sum(c["usage"].get("input_tokens", 0) for c in llm),
        "out_tokens": sum(c["usage"].get("output_tokens", 0) for c in llm),
        "browser_checks": sum(1 for t in new if t["type"] == "tool_call_started" and t["payload"]["name"].startswith("browser_")),
        "verifier_calls": sum(
            1 for t in new if t["type"] == "tool_call_started" and t["payload"].get("arguments", {}).get("agent") == "verifier"
        ),
    }


def main() -> None:
    args = parse()
    home = RUNS / f"bench_{args.name}_home"
    workspace = RUNS / f"bench_{args.name}"
    home.mkdir(parents=True, exist_ok=True)
    if args.config:
        (home / "config.yaml").write_text(args.config, encoding="utf-8")
    env = {**os.environ, "FORGE_HOME": str(home), "FORGE_ENV_FILE": str(FORGE / ".env"), "PYTHONIOENCODING": "utf-8"}
    for pair in args.env:
        key, _, value = pair.partition("=")
        env[key] = value
    if not workspace.exists():
        subprocess.run(
            [str(PYTHON), "-m", "forge.cli", "new", "--standalone", "--project", f"bench-{args.name}", "--workspace", str(workspace)],
            env=env, check=True, capture_output=True,
        )
    events_path = workspace / ".forge" / "transcripts" / "events.jsonl"
    seq = 0
    results = []
    for title, prompt_path, phase in STEPS:
        prompt = prompt_path.read_text(encoding="utf-8").replace("5055", args.port)
        prompt_file = RUNS / f"bench_{args.name}_{phase}.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        out_json = RUNS / f"bench_{args.name}_{phase}.json"
        out_json.unlink(missing_ok=True)
        started = time.time()
        subprocess.run(
            [str(PYTHON), str(CAMPAIGN / "drive_forge.py"), str(workspace), str(prompt_file), str(out_json)],
            env=env, capture_output=True,
        )
        wall = round(time.time() - started)
        summary = run_summary(events_path, seq) if events_path.exists() else {"last_seq": seq}
        seq = int(summary.pop("last_seq"))
        verify = subprocess.run(
            [str(PYTHON), str(CAMPAIGN / "verify_attendance.py"), str(workspace / "project"), str(workspace / ".venv" / "Scripts" / "python.exe"), str(phase)],
            env={**env, "APP_PORT": args.port}, capture_output=True, text=True,
        )
        match = re.search(r"(\d+)/(\d+) checks passed", verify.stdout)
        failed = [line[:140] for line in verify.stdout.splitlines() if line.startswith("FAIL")]
        results.append(
            {"step": title, "wall_s": wall, **summary, "checks": match.group(0) if match else "no result", "failed": failed}
        )
        print(f"[{args.name}] {title}: {wall}s, {summary.get('model_calls')} calls, {results[-1]['checks']}", flush=True)
        (RUNS / f"bench_{args.name}.json").write_text(
            json.dumps({"name": args.name, "env": args.env, "config": args.config, "started": datetime.now().isoformat(), "steps": results}, indent=1),
            encoding="utf-8",
        )
    total = sum(r["wall_s"] for r in results)
    print(f"[{args.name}] total {total}s", flush=True)


if __name__ == "__main__":
    sys.exit(main())
