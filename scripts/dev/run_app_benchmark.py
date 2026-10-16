"""Run DebCraft on the business-application briefs and keep everything needed to judge it (docs/APP_BENCHMARK.md).

`python scripts/dev/run_app_benchmark.py hr_leave bank_loan supply_p2p [--out C:\\Work\\ForgeRuns\\forge-apps] [--coder gpt54] [--timeout-min 150]`

For each brief in tests/benchmarks/apps/<id>/prompt.md: a fresh workspace and its own DebCraft home, the headless driver (questions get "use your best judgement" and are recorded as events), the wall time, and `run.json`.
Scoring is a separate step (scripts/dev/score_app.py). Nothing here touches the user's real DebCraft folder."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "overnight"))
from fsutil import remove_tree  # noqa: E402


def run_one(app_id: str, out: Path, coder: str, timeout_min: int, env_file: str) -> dict[str, object]:
    run_dir = out / app_id
    remove_tree(run_dir)
    run_dir.mkdir(parents=True)
    home, workspace = run_dir / "home", run_dir / "ws"
    home.mkdir()
    if coder:
        roles = ["coder", "kb_builder", "summariser", "vision"]
        lines = ["llm:", "  roles:", *[f"    {role}: {coder}" for role in roles]]
        (home / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    env = {**os.environ, "FORGE_HOME": str(home), "PYTHONIOENCODING": "utf-8"}
    if env_file:
        env["FORGE_ENV_FILE"] = env_file
    created = subprocess.run(
        [sys.executable, "-m", "forge.cli", "new", "--standalone", "--project", f"app-{app_id}", "--workspace", str(workspace)],
        env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, check=False,
    )  # fmt: skip
    if created.returncode != 0:
        return {"id": app_id, "error": (created.stdout + created.stderr)[-400:]}
    prompt = REPO / "tests" / "benchmarks" / "apps" / app_id / "prompt.md"
    started = time.time()
    timed_out = False
    try:
        driven = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "campaign" / "drive_forge.py"), str(workspace), str(prompt), str(run_dir / "run.json")],
            env=env, capture_output=True, timeout=timeout_min * 60, check=False,
        )  # fmt: skip
        (run_dir / "drive.log").write_text(
            (driven.stdout + driven.stderr).decode("utf-8", errors="replace")[-20000:], encoding="utf-8"
        )
    except subprocess.TimeoutExpired:
        timed_out = True
    row = {
        "id": app_id,
        "seconds": round(time.time() - started),
        "timed_out": timed_out,
        "workspace": str(workspace),
    }
    (run_dir / "result.json").write_text(json.dumps(row, indent=1), encoding="utf-8")
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("apps", nargs="+")
    parser.add_argument("--out", default=r"C:\Work\ForgeRuns\forge-apps")
    parser.add_argument("--coder", default="gpt54")
    parser.add_argument("--timeout-min", type=int, default=150)
    parser.add_argument("--env-file", default=os.environ.get("FORGE_ENV_FILE", ""))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for app_id in args.apps:
        print(f"[{time.strftime('%H:%M:%S')}] START {app_id}", flush=True)
        row = run_one(app_id, out, args.coder, args.timeout_min, args.env_file)
        print(f"[{time.strftime('%H:%M:%S')}] END   {app_id}: {row}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
