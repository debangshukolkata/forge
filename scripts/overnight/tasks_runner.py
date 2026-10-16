"""Gives DebCraft one overnight task and checks what it delivered.

    python scripts/overnight/tasks_runner.py <task-id> --out <folder> [--env-file <.env>] [--timeout-min N]

A task is a folder in tests/benchmarks/overnight (task.json, prompt.md, optional seed/). The run makes a fresh workspace and its own DebCraft home under <folder>/<task-id>/, copies the
seed files in, runs DebCraft headless on the prompt (the model may install packages into the workspace's own environment, nothing else), then runs the task's checks
(verify_tasks.py). It writes task_result.json and task_result.md and exits 0 when DebCraft finished, whatever the checks say: a failed check is a result, not a crash."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from make_signature_sample import make as make_signature_sample  # noqa: E402
from verify_tasks import kill_tree, verify  # noqa: E402

TASKS = REPO / "tests" / "benchmarks" / "overnight"


def load_task(task_id: str) -> tuple[dict[str, object], Path]:
    folder = TASKS / task_id
    return json.loads((folder / "task.json").read_text(encoding="utf-8")), folder


def prepare(
    task: dict[str, object], folder: Path, run_dir: Path, env: dict[str, str], default_coder: str = ""
) -> Path:
    """The workspace with the seed files (and the generated sample) in place."""
    workspace = run_dir / "ws"
    home = run_dir / "home"
    home.mkdir(parents=True, exist_ok=True)
    roles: dict[str, str] = {}
    if (
        default_coder and default_coder != "gpt51"
    ):  # the isolated home has no saved plan: give the builder roles the model the user's own plan would (D-446)
        roles = {role: default_coder for role in ("coder", "kb_builder", "summariser", "vision")}
    given = task.get("roles")
    if isinstance(given, dict):
        roles.update({str(role): str(model) for role, model in given.items()})
    if roles:
        lines = ["llm:", "  roles:", *[f"    {role}: {model}" for role, model in roles.items()]]
        (home / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    created = subprocess.run(
        [sys.executable, "-m", "forge.cli", "new", "--standalone", "--project", f"overnight-{task['id']}", "--workspace", str(workspace)],
        env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, check=False,
    )  # fmt: skip
    if created.returncode != 0:
        raise RuntimeError(f"workspace setup failed: {(created.stdout + created.stderr)[-400:]}")
    project = workspace / "project"
    project.mkdir(parents=True, exist_ok=True)
    seed = folder / "seed"
    if seed.is_dir():
        shutil.copytree(seed, project, dirs_exist_ok=True)
    if task.get("generate") == "sigcrop":
        make_signature_sample(project, 7)
        (project / "prescription.jpg.truth.json").unlink(
            missing_ok=True
        )  # the answer stays out of the workspace
    return workspace


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    parser.add_argument("--out", required=True)
    parser.add_argument("--env-file", default="")
    parser.add_argument("--timeout-min", type=int, default=0)
    parser.add_argument("--default-coder", default="")
    args = parser.parse_args()
    task, folder = load_task(args.task)
    run_dir = Path(args.out) / str(task["id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "FORGE_HOME": str(run_dir / "home"), "PYTHONIOENCODING": "utf-8", "CI": "1"}
    if args.env_file:
        env["FORGE_ENV_FILE"] = args.env_file
    result: dict[str, object] = {
        "task": task["id"],
        "title": task["title"],
        "kind": task.get("kind", ""),
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    started = time.time()
    status = "finished"
    try:
        workspace = prepare(task, folder, run_dir, env, args.default_coder)
        prompt = run_dir / "prompt.txt"
        prompt.write_text((folder / "prompt.md").read_text(encoding="utf-8"), encoding="utf-8")
        timeout = (args.timeout_min or int(str(task.get("timeout_min", 40)))) * 60
        log = (run_dir / "forge_console.log").open("w", encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, str(REPO / "scripts" / "campaign" / "drive_forge.py"), str(workspace), str(prompt), str(run_dir / "run.json")],
            env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
        )  # fmt: skip
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            kill_tree(process)
            status = "timeout"
        log.close()
        if status == "finished" and process.returncode not in (0, None):
            status = f"exit code {process.returncode}"
        result["forge_seconds"] = round(time.time() - started)
        outcome = verify(task, workspace, run_dir, REPO)
        result.update(
            {
                "status": status,
                "checks": outcome["checks"],
                "passed": outcome["passed"],
                "total": outcome["total"],
                "evidence": outcome["evidence"],
            }
        )
        events = workspace / ".forge" / "transcripts" / "events.jsonl"
        result["events_file"] = str(events) if events.is_file() else ""
        shots = (
            sorted((workspace / ".forge" / "screenshots").glob("*.png"))[-4:]
            if (workspace / ".forge" / "screenshots").is_dir()
            else []
        )
        result["forge_screenshots"] = [str(p) for p in shots]
    except Exception as error:  # the runner's own failure is a result too
        result.update(
            {
                "status": f"runner error: {type(error).__name__}: {error}",
                "checks": [],
                "passed": 0,
                "total": 0,
                "evidence": [],
            }
        )
    result["seconds"] = round(time.time() - started)
    (run_dir / "task_result.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    lines = [
        f"# {task['title']}",
        "",
        f"Status: {result['status']} in {result['seconds']} s. Checks passed: {result.get('passed', 0)} of {result.get('total', 0)}.",
        "",
    ]
    for item in result.get("checks", []):  # type: ignore[attr-defined]
        lines.append(
            f"- {'PASS' if item['ok'] else 'FAIL'}: {item['name']}"
            + (f" ({item['detail']})" if item["detail"] and not item["ok"] else "")
        )
    (run_dir / "task_result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
