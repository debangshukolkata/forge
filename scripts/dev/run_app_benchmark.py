"""Run DebCraft on the business-application briefs and keep everything needed to judge it (docs/APP_BENCHMARK.md).

`python scripts/dev/run_app_benchmark.py hr_leave bank_loan supply_p2p [--out C:\\Work\\ForgeRuns\\forge-apps] [--coder gpt54] [--timeout-min 150]`

For each brief in tests/benchmarks/apps/<id>/prompt.md: a fresh workspace and its own DebCraft home, the headless driver (questions get "use your best judgement" and are recorded as events), the wall time, and `run.json`.
Scoring is a separate step (scripts/dev/score_app.py). Nothing here touches the user's real DebCraft folder."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "overnight"))

from fsutil import remove_tree  # noqa: E402

PLANNING_WRITES = ("DESIGN.md", "NOTICES.md", "ASSUMPTIONS.md", "ANALYSIS.md", "PRODUCT.md")


def building_started(events: Path) -> str:
    """The first write of a real project file (not DESIGN.md, notes or the design candidates): from here on DebCraft is building, and the analysis, questions, plan and decisions are already in the log."""
    if not events.is_file():
        return ""
    for line in events.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        payload = event.get("payload", {})
        if event.get("type") != "tool_call_started" or payload.get("name") not in (
            "write_file",
            "multi_edit",
            "run_command",
        ):
            continue
        path = str((payload.get("arguments") or {}).get("path") or "").replace("\\", "/")
        if payload.get("name") == "run_command":
            command = str((payload.get("arguments") or {}).get("command") or "").lower()
            if "pip install" in command or "uv " in command:
                return f"run_command at {event['ts'][11:19]}"
            continue
        if path and not path.startswith(".forge") and path.split("/")[-1] not in PLANNING_WRITES:
            return f"{payload['name']} {path} at {event['ts'][11:19]}"
    return ""


def kill_tree(pid: int) -> None:
    import psutil

    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    for process in [*parent.children(recursive=True), parent]:
        with contextlib.suppress(psutil.NoSuchProcess):
            process.kill()


def run_one(
    app_id: str,
    out: Path,
    coder: str,
    timeout_min: int,
    env_file: str,
    stop_at_build: bool,
    planner_effort: str = "",
) -> dict[str, object]:
    run_dir = out / app_id
    remove_tree(run_dir)
    run_dir.mkdir(parents=True)
    home, workspace = run_dir / "home", run_dir / "ws"
    home.mkdir()
    lines = ["llm:"]
    if coder:
        roles = ["coder", "kb_builder", "summariser", "vision"]
        lines += ["  roles:", *[f"    {role}: {coder}" for role in roles]]
    if planner_effort:
        lines += ["  role_reasoning_effort:", f"    planner: {planner_effort}"]
    if len(lines) > 1:
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
    command = [
        sys.executable,
        str(REPO / "scripts" / "campaign" / "drive_forge.py"),
        str(workspace),
        str(prompt),
        str(run_dir / "run.json"),
    ]
    log = (run_dir / "drive.log").open("wb")
    process = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT)
    stopped_at = ""
    events = workspace / ".forge" / "transcripts" / "events.jsonl"
    try:
        while process.poll() is None:
            if time.time() - started > timeout_min * 60:
                timed_out = True
                break
            if stop_at_build and (hit := building_started(events)):
                time.sleep(10)  # let the planning events and the first writes reach the log
                stopped_at = hit
                break
            time.sleep(4)
    finally:
        if process.poll() is None:
            kill_tree(process.pid)
        log.close()
    row = {
        "id": app_id,
        "seconds": round(time.time() - started),
        "timed_out": timed_out,
        "stopped_when_building_began": stopped_at,
        "workspace": str(workspace),
    }
    (run_dir / "result.json").write_text(json.dumps(row, indent=1), encoding="utf-8")
    return row


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("apps", nargs="+")
    parser.add_argument("--out", default=r"C:\Work\ForgeRuns\forge-apps")
    parser.add_argument("--coder", default="gpt54")
    parser.add_argument(
        "--planner-effort", default="", help="reasoning effort for the planner role only: low, medium, high"
    )
    parser.add_argument("--timeout-min", type=int, default=150)
    parser.add_argument(
        "--full",
        action="store_true",
        help="let DebCraft build the whole application (default: stop when building begins, the planning layer is what is judged)",
    )
    parser.add_argument("--env-file", default=os.environ.get("FORGE_ENV_FILE", ""))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for app_id in args.apps:
        print(f"[{time.strftime('%H:%M:%S')}] START {app_id}", flush=True)
        row = run_one(
            app_id, out, args.coder, args.timeout_min, args.env_file, not args.full, args.planner_effort
        )
        print(f"[{time.strftime('%H:%M:%S')}] END   {app_id}: {row}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
