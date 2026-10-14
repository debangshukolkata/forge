"""Approach challenges (TODO part 4): give DebCraft a small task with one trap, stop the run early, and judge the APPROACH from the event log.

    python scripts/benchmark/run_challenges.py <run-name> [--tasks c01_month_boundary,c04_lost_counts] [--max-seconds 300] [--max-tool-calls 20] [--env KEY=VALUE ...]

Each run is stopped after `--max-tool-calls` tool calls or `--max-seconds`, whichever comes first: the point is how the problem is approached (what is read first, whether the
requirement is questioned, whether a failing test or a check comes before the fix, whether a library is checked before it is used), not whether the code is finished.
Results: C:\\Work\\ForgeRuns\\challenges\\<run-name>\\<id>_timeline.txt (what happened, in order), results.json and a table with the automatic signals.
The judgement is made by reading the timeline against tests/benchmarks/challenges/README.md. It spends Azure tokens (a few cents per challenge)."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_code_benchmark import PYTHON, REPO

CHALLENGES = REPO / "tests" / "benchmarks" / "challenges"
RUNS = Path(os.environ.get("FORGE_BENCH_RUNS", r"C:\Work\ForgeRuns")) / "challenges"
READ_TOOLS = {"read_file", "grep", "glob", "list_dir", "search_files", "library_api", "lsp_symbols"}
EDIT_TOOLS = {"write_file", "edit_file", "multi_edit", "delete_file", "move_file"}
ASK_TOOLS = {"ask_user", "propose_requirements", "propose_plan"}
APPROVAL = "\n\nYou may install packages with `python -m pip install ...` in this project's environment: that is approved."


def read_events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    return events


def count_tools(events: list[dict[str, object]]) -> int:
    return sum(1 for e in events if e["type"] == "tool_call_started")


def kill_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
    else:
        process.kill()


def is_test_path(path: str) -> bool:
    name = path.replace("\\", "/").lower()
    return "/tests/" in "/" + name or Path(name).name.startswith("test_") or name.endswith("_test.py")


def timeline(events: list[dict[str, object]]) -> tuple[str, dict[str, object]]:
    """A readable account of the run and the automatic signals taken from it."""
    lines: list[str] = []
    calls: list[tuple[str, str, dict[str, object]]] = []  # name, summary, arguments
    for e in events:
        payload: dict[str, object] = e["payload"]  # type: ignore[assignment]
        stamp = str(e["ts"])[11:19]
        if e["type"] == "user_message":
            lines.append(f"{stamp} USER   {str(payload.get('text'))[:300]}")
        elif e["type"] == "message_done":
            lines.append(f"{stamp} MODEL  {str(payload.get('text', '')).strip()[:700]}")
        elif e["type"] == "tool_call_started":
            name = str(payload.get("name"))
            arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
            calls.append((name, str(payload.get("summary")), arguments))  # type: ignore[arg-type]
            lines.append(f"{stamp} #{len(calls):02d} {name}: {str(payload.get('summary'))[:130]}")
        elif e["type"] == "tool_call_finished" and not payload.get("ok", True):
            lines.append(f"{stamp}      FAILED: {str(payload.get('preview'))[:160]}")
        elif e["type"] == "thinking_delta" and str(payload.get("text", "")).strip():
            lines.append(f"{stamp}      (thinking) {str(payload.get('text')).strip()[:200]}")
    first_edit = next(
        (
            i
            for i, (name, _, args) in enumerate(calls)
            if name in EDIT_TOOLS and not is_test_path(str(args.get("path", "")))
        ),
        None,
    )
    first_any_edit = next((i for i, (name, _, _) in enumerate(calls) if name in EDIT_TOOLS), None)
    first_source_edit = first_edit
    before = calls[:first_any_edit] if first_any_edit is not None else calls

    def ran_tests(items: list[tuple[str, str, dict[str, object]]]) -> bool:
        return any(
            name in ("run_command", "python_run") and "pytest" in (summary + str(args))
            for name, summary, args in items
        )

    test_before_source = False
    if first_source_edit is not None:
        test_before_source = any(
            name in EDIT_TOOLS and is_test_path(str(args.get("path", "")))
            for name, _, args in calls[:first_source_edit]
        )
    asked = any(name in ASK_TOOLS for name, _, _ in before)
    stated = any(
        e["type"] == "message_done"
        and re.search(
            r"assum|ambigu|unclear|not specified|decid(e|ed) to|I'll treat",
            str(e["payload"].get("text", "")),
            re.I,
        )  # type: ignore[union-attr]
        for e in events
    )
    signals: dict[str, object] = {
        "tool_calls": len(calls),
        "reads_before_first_edit": sum(1 for name, _, _ in before if name in READ_TOOLS),
        "tests_run_before_first_edit": ran_tests(before),
        "test_written_before_source_edit": test_before_source,
        "first_edit": None
        if first_any_edit is None
        else f"#{first_any_edit + 1} {calls[first_any_edit][0]} {calls[first_any_edit][2].get('path', '')}",
        "asked_or_planned_before_editing": asked,
        "assumptions_mentioned": stated,
        "library_checked": any(
            name == "library_api"
            or (
                name in ("run_command", "python_run")
                and re.search(r"pip (show|list|freeze)|help\(|__version__|inspect\.", summary + str(args))
            )
            for name, summary, args in calls
        ),
    }
    return "\n".join(lines), signals


def file_checks(challenge: str, workspace: Path, events: list[dict[str, object]]) -> dict[str, object]:
    """Signals that need the content the model wrote (the arguments of its write calls)."""
    written = "\n".join(
        str(e["payload"]["arguments"].get("content", "")) + str(e["payload"]["arguments"].get("new_text", ""))  # type: ignore[index, union-attr]
        for e in events
        if e["type"] == "tool_call_started"
        and e["payload"].get("name") in EDIT_TOOLS
        and isinstance(e["payload"].get("arguments"), dict)  # type: ignore[union-attr]
    )
    if challenge == "c05_product_search":
        return {
            "parameterized_like": bool(re.search(r"LIKE\s+\?", written, re.I)),
            "f_string_sql": bool(re.search(r"f[\"'].*(SELECT|LIKE)", written)),
        }
    if challenge == "c07_settings_model":
        return {
            "v1_api_used": bool(re.search(r"@validator|parse_obj|class Config|\.dict\(\)", written)),
            "v2_api_used": bool(re.search(r"field_validator|model_validate|model_dump", written)),
        }
    if challenge == "c04_lost_counts":
        return {"lock_added": bool(re.search(r"Lock\(|RLock|atomic", written))}
    if challenge == "c06_csv_export":
        return {
            "uses_format_money": "format_money" in written,
            "uses_result": "Result" in written,
            "uses_csv_module": bool(re.search(r"import csv|csv\.", written)),
        }
    if challenge == "c01_month_boundary":
        return {
            "fix_in_timeutil": "timeutil" in written
            or bool(re.search(r"ZoneInfo|zoneinfo|astimezone", written))
        }
    return {}


def run_challenge(
    task: Path, run_dir: Path, env: dict[str, str], max_seconds: int, max_tools: int
) -> dict[str, object]:
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
            f"challenge-{meta['id']}",
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
            "error": f"workspace setup failed: {created.stdout[-300:]}{created.stderr[-300:]}",
        }
    if (task / "seed").exists():
        shutil.copytree(task / "seed", workspace / "project", dirs_exist_ok=True)
    prompt = (task / "task.md").read_text(encoding="utf-8")
    if "approved" not in prompt:
        prompt += APPROVAL
    prompt_file = run_dir / f"{meta['id']}_prompt.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    process = subprocess.Popen(
        [
            str(PYTHON),
            str(REPO / "scripts" / "campaign" / "drive_forge.py"),
            str(workspace),
            str(prompt_file),
            str(run_dir / f"{meta['id']}_run.json"),
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )
    started = time.time()
    events_path = workspace / ".forge" / "transcripts" / "events.jsonl"
    reason = "finished"
    while process.poll() is None:
        time.sleep(3)
        if time.time() - started > max_seconds:
            reason = f"time box ({max_seconds} s)"
            break
        if count_tools(read_events(events_path)) >= max_tools:
            reason = f"{max_tools} tool calls"
            break
    kill_tree(process)
    time.sleep(1)
    events = read_events(events_path)
    text, signals = timeline(events)
    (run_dir / f"{meta['id']}_timeline.txt").write_text(text + "\n", encoding="utf-8")
    row: dict[str, object] = {
        "id": meta["id"],
        "trap": meta["trap"],
        "stopped": reason,
        "seconds": round(time.time() - started),
    }
    row.update(signals)
    row.update(file_checks(meta["id"], workspace, events))
    return row


def markdown(name: str, rows: list[dict[str, object]]) -> str:
    lines = [f"### Challenges `{name}` ({time.strftime('%Y-%m-%d %H:%M')})", ""]
    for row in rows:
        if "error" in row:
            lines.append(f"- {row['id']}: ERROR {row['error']}")
            continue
        facts = ", ".join(f"{k}={v}" for k, v in row.items() if k not in ("id", "trap"))
        lines.append(f"- **{row['id']}** (trap: {row['trap']}): {facts}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name")
    parser.add_argument("--tasks", default="")
    parser.add_argument("--max-seconds", type=int, default=300)
    parser.add_argument("--max-tool-calls", type=int, default=20)
    parser.add_argument("--env", action="append", default=[])
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
    rows: list[dict[str, object]] = []
    for task in sorted(
        p for p in CHALLENGES.iterdir() if (p / "task.json").exists() and (not wanted or p.name in wanted)
    ):
        print(f"[{args.name}] {task.name} ...", flush=True)
        rows.append(run_challenge(task, run_dir, env, args.max_seconds, args.max_tool_calls))
        (run_dir / "results.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    report = markdown(args.name, rows)
    (run_dir / "results.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
