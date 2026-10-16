"""The overnight runner: runs every job once, one after another, and leaves a morning report.

    python scripts/overnight/run_overnight.py --env-file "%USERPROFILE%\\.forge\\.env" [--profile core|extended] [--max-hours 11] [--out <folder>] [--only id,id] [--skip id,id] [--dry-run]

What it guarantees (the point of the night):
- Each job is its own process with a time limit and a stall limit: if nothing it writes (output, events, results) changes for 25 minutes it is stopped, marked STALLED, and the night goes on.
- The whole night has a time budget (--max-hours); no job is started that cannot finish in what is left, and a running job is stopped at the budget.
- A job needs capabilities (Azure, Gemini, npm, a browser...). The preflight finds out which exist; a job that needs a missing one is SKIPPED with the reason, never started.
- Nothing reads the keyboard (stdin is closed), the machine is asked to stay awake, and one instance only can run in a folder.
- After every job the state, MORNING_REPORT.md and MORNING_REPORT.html are rewritten, so a night that is cut short still has a report. A job that failed gets a failure.md (what it ran, how it ended,
  the console tail, the last events of the model run, the failed checks) and up to ten pictures in evidence/. Run it again with the same --out to continue where a stopped night ended.
- At the end results-bundle.zip holds the report and the small files of every job (redacted); the large workspaces stay in runs/."""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
from fsutil import remove_tree  # noqa: E402
from jobs import Ctx, Job, catalogue  # noqa: E402
from report import redact, write_report  # noqa: E402
from verify_tasks import kill_tree  # noqa: E402

sys.path.insert(0, str(REPO / "src"))
from forge.toolkit.private_env import without_store_aliases  # noqa: E402

POLL_S = 10
STOP_AFTER_JOB = (
    "STOP"  # a file in the run folder: finish the job that is running, then stop (Pause-Overnight.cmd)
)
STOP_NOW = "STOP_NOW"  # a file in the run folder: stop the running job now; it runs again from its start on resume (Pause-Overnight-Now.cmd)
DONE = {"PASS", "PROBLEMS", "FAILED", "TIMEOUT", "STALLED"}
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def keep_awake() -> None:
    with contextlib.suppress(Exception):
        spec = importlib.util.spec_from_file_location("awake", REPO / "scripts" / "benchmark" / "awake.py")
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.keep_awake()


# --- preflight -----------------------------------------------------------------------------------------------------------------


def run_quiet(argv: list[str], timeout: int, env: dict[str, str] | None = None) -> tuple[int, str]:
    try:
        done = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            env=env,
            cwd=REPO,
        )
        return done.returncode, done.stdout + done.stderr
    except (subprocess.TimeoutExpired, OSError) as error:
        return 1, f"{type(error).__name__}: {error}"


def env_names(path: str) -> list[str]:
    names: list[str] = []
    with contextlib.suppress(OSError):
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.match(r"^\s*(?:export\s+)?([A-Za-z0-9_]+)\s*=\s*\S", line)
            if match:
                names.append(match.group(1))
    return sorted(set(names))


def preflight(ctx: Ctx) -> tuple[dict[str, bool], str]:
    caps: dict[str, bool] = {}
    notes: list[str] = [f"python {platform.python_version()} on {platform.platform()}", f"repository {REPO}"]
    caps["pytest"] = importlib.util.find_spec("pytest") is not None
    caps["xdist"] = importlib.util.find_spec("xdist") is not None
    caps["playwright"] = importlib.util.find_spec("playwright") is not None
    caps["node"] = bool(shutil.which("node") and shutil.which("npm"))
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    caps["edge"] = caps["playwright"] and (
        any(Path(p).is_file() for p in edge_paths) or bool(shutil.which("msedge") or shutil.which("chrome"))
    )
    notes.append("tools: " + ", ".join(f"{name} {'yes' if value else 'NO'}" for name, value in caps.items()))
    notes.append(
        "tesseract: "
        + (shutil.which("tesseract") or "not on PATH (DebCraft looks in the usual folders itself)")
    )
    notes.append(
        "names in the .env file: "
        + (", ".join(env_names(ctx.env_file)) or "none found (is --env-file right?)")
    )
    models: dict[str, Any] = {}
    code, text = run_quiet(
        [ctx.python, str(HERE / "probe_models.py"), *(["--env-file", ctx.env_file] if ctx.env_file else [])],
        400,
    )
    try:
        newline = chr(10)
        start = (
            0 if text.startswith("{" + newline) else text.index(newline + "{" + newline) + 1
        )  # warnings before the JSON are skipped
        models, _ = json.JSONDecoder().raw_decode(
            text[start:]
        )  # and so is the noise some libraries print after it when the process ends
    except ValueError:
        notes.append("model probe failed: " + text[-300:])
    models.pop("_azure_seconds", None)
    for key, result in sorted(models.items()):
        said = result.get("detail") if result.get("ok") else result.get("error")
        notes.append(
            f"model {key}: {'answers' if result.get('ok') else 'NO ANSWER'}: {str(said or '')[:300]}"
        )
    caps["azure"] = any(models.get(k, {}).get("ok") for k in ("gpt51", "gpt41", "gpt4o", "gpt54", "gpt52"))
    caps["azure_strong"] = bool(models.get("gpt54", {}).get("ok"))
    caps["gemini"] = any(r.get("ok") for k, r in models.items() if k.startswith("gemini"))
    caps["gemini_argon"] = bool(models.get("gemini4argon", {}).get("ok"))
    if caps["gemini"]:
        code, text = run_quiet([ctx.python, str(REPO / "scripts" / "dev" / "image_smoke.py")], 240)
        caps["image"] = code == 0
        notes.append(f"generate_image: {'works' if code == 0 else 'FAILED: ' + text[-200:]}")
    code, text = run_quiet([ctx.python, "-m", "forge.cli", "doctor"], 240)
    (ctx.out / "doctor.txt").write_text(redact(text), encoding="utf-8")
    notes.append("forge doctor saved in doctor.txt")
    (ctx.out / "preflight.json").write_text(
        json.dumps({"caps": caps, "models": models}, indent=1), encoding="utf-8"
    )
    return caps, "\n".join(notes)


# --- one job -------------------------------------------------------------------------------------------------------------------


def activity(paths: list[Path], log_file: Path) -> tuple[float, int]:
    """(the newest modification time of the files a job writes, the size of its console log): unchanged for the stall limit means the job is stuck."""
    newest = 0.0
    for root in paths:
        if not root.exists():
            continue
        for folder, dirs, files in os.walk(root):
            dirs[:] = [
                d for d in dirs if d not in {"node_modules", ".venv", ".git", "__pycache__", ".pytest_cache"}
            ]
            for name in files:
                with contextlib.suppress(OSError):
                    newest = max(newest, os.stat(os.path.join(folder, name)).st_mtime)
    size = log_file.stat().st_size if log_file.exists() else 0
    return newest, size


def tail(path: Path, count: int) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-count:])
    except OSError:
        return ""


def newest_events(root: Path) -> Path | None:
    found = sorted(root.rglob("events.jsonl"), key=lambda p: p.stat().st_mtime) if root.exists() else []
    return found[-1] if found else None


def events_tail(path: Path, count: int = 40) -> str:
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - 400_000))
            raw = handle.read().decode("utf-8", errors="replace").splitlines()[-count:]
    except OSError:
        return ""
    lines = []
    for line in raw:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        payload = event.get("payload", {})
        detail = (
            payload.get("name")
            or payload.get("summary")
            or payload.get("message")
            or payload.get("text")
            or payload.get("state")
            or ""
        )
        lines.append(f"{str(event.get('ts', ''))[11:19]} {event.get('type', '')} {str(detail)[:150]}")
    return "\n".join(lines)


def analyse(job: Job, code: int | None, ended: str, job_dir: Path, ctx: Ctx) -> tuple[str, str, list[str]]:
    """(status, a one-line finding, the details for failure.md) from how the job ended and what it wrote."""
    console = tail(job_dir / "console.log", 400)
    details: list[str] = []
    if ended == "INTERRUPTED":
        return "INTERRUPTED", "stopped on request; it runs again from its start when you resume", details
    if ended in ("STALLED", "TIMEOUT"):
        return (
            ended,
            "stopped by the runner: "
            + ("nothing changed for too long" if ended == "STALLED" else "over its time limit"),
            details,
        )
    if job.kind == "pytest":
        summary = [line for line in console.splitlines() if re.search(r"\d+ (passed|failed|error)", line)]
        failed = [line for line in console.splitlines() if line.startswith(("FAILED", "ERROR"))]
        details += failed[:30]
        finding = summary[-1].strip() if summary else console.splitlines()[-1] if console else "no output"
        return ("PASS" if code == 0 else "PROBLEMS" if code == 1 else "FAILED"), finding, details
    if job.kind == "tasks":
        result_file = ctx.runs / job.run_root / "task_result.json"
        try:
            result = json.loads(result_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return "FAILED", "the task runner wrote no result", details
        failed_checks = [f"{c['name']}: {c['detail']}" for c in result.get("checks", []) if not c["ok"]]
        details += failed_checks
        finding = f"{result.get('status')}; checks {result.get('passed', 0)}/{result.get('total', 0)} in {result.get('seconds', 0)} s"
        if str(result.get("status", "")).startswith("timeout"):
            return "TIMEOUT", finding, details
        if str(result.get("status", "")) != "finished":
            return "FAILED", finding, details
        return ("PASS" if not failed_checks else "PROBLEMS"), finding, details
    if job.kind == "benchmark":
        results = ctx.runs / job.results_glob
        if code not in (0, None) or not results.is_file():
            return (
                "FAILED",
                f"exit code {code}; "
                + ("no results.md was written" if not results.is_file() else "results exist"),
                details,
            )
        text = results.read_text(encoding="utf-8", errors="replace")
        errors = [
            line
            for line in text.splitlines()
            if "ERROR" in line or "timed out" in line.lower() or "INVALID" in line
        ]
        rows = [
            line
            for line in text.splitlines()
            if line.startswith("|") and not line.startswith(("|---", "| Brief", "| Task"))
        ]
        details += errors[:20]
        return (
            ("PROBLEMS" if errors else "PASS"),
            f"{len(rows)} result row(s), {len(errors)} with errors or timeouts",
            details,
        )
    last = [line for line in console.splitlines() if line.strip()]
    return ("PASS" if code == 0 else "FAILED"), (last[-1][:200] if last else "no output"), details


def collect_evidence(job: Job, job_dir: Path, ctx: Ctx) -> list[str]:
    """Copy the pictures worth looking at, and the results files, into the job folder (small files only)."""
    evidence = job_dir / "evidence"
    evidence.mkdir(exist_ok=True)
    root = ctx.runs / job.run_root if job.run_root else None
    picked: list[Path] = []
    if root and root.exists():
        for pattern in (
            "**/*_shots/*.png",
            "**/page-*.png",
            "**/signature-*-on-white.png",
            "**/.forge/screenshots/*.png",
            "**/specimen-*.png",
        ):
            found = sorted(
                (p for p in root.glob(pattern) if ".venv" not in p.parts), key=lambda p: p.stat().st_mtime
            )
            picked += found[-6:] if "screenshots" in pattern else found[:6]
        for name in (
            "results.md",
            "results.json",
            "task_result.md",
            "task_result.json",
            "verify.json",
            "forge_console.log",
            "key.md",
            "gallery.html",
        ):
            for item in list(root.glob(name))[:1]:
                with contextlib.suppress(OSError):
                    shutil.copy(item, job_dir / item.name)
    names: list[str] = []
    for index, item in enumerate(dict.fromkeys(picked)):
        if item.suffix.lower() in IMAGE_SUFFIXES and item.stat().st_size < 3_000_000 and index < 10:
            name = f"{index:02d}-{item.parent.name[:20]}-{item.name}"[:90]
            with contextlib.suppress(OSError):
                shutil.copy(item, evidence / name)
                names.append(name)
    return names


def write_failure(
    job: Job,
    status: str,
    finding: str,
    details: list[str],
    code: int | None,
    seconds: float,
    argv: list[str],
    job_dir: Path,
    ctx: Ctx,
    evidence: list[str],
) -> None:
    events = newest_events(ctx.runs / job.run_root) if job.run_root else None
    parts = [
        f"# {job.title}: {status}",
        "",
        f"- Job: `{job.id}` ({job.group}); ended after {int(seconds)} s with exit code {code}.",
        f"- What it found: {finding}",
        f"- Command: `{' '.join(argv)}`",
        "",
        "## What went wrong (the failed checks, tests or rows)",
        "",
        *(f"- {line}" for line in details[:40]),
        "" if details else "(the runner has no more detail; see the console tail)",
        "",
        "## The last lines of the console",
        "",
        "```",
        tail(job_dir / "console.log", 70),
        "```",
        "",
    ]
    if events:
        parts += [
            "## The last events of the model run (what it was doing)",
            "",
            f"From {events}",
            "",
            "```",
            events_tail(events),
            "```",
            "",
        ]
    parts += ["## Pictures saved with this failure", "", *(f"- evidence/{name}" for name in evidence), ""]
    (job_dir / "failure.md").write_text(redact("\n".join(parts)), encoding="utf-8")


def strip_xdist(argv: list[str]) -> list[str]:
    cleaned: list[str] = []
    skip = 0
    for arg in argv:
        if skip:
            skip -= 1
        elif arg in ("-n", "--dist"):
            skip = 1
        else:
            cleaned.append(arg)
    return cleaned


def run_job(job: Job, ctx: Ctx, deadline: float, entry: dict[str, Any], save: Any) -> None:
    job_dir = ctx.out / "jobs" / job.id
    if job_dir.exists():  # an earlier attempt (stopped, or failed and run again): keep its small files as <id>-previous, start the job clean
        previous = ctx.out / "jobs" / f"{job.id}-previous"
        remove_tree(previous)
        with contextlib.suppress(OSError):
            job_dir.rename(previous)
    if job.run_root and (ctx.runs / job.run_root).exists():
        remove_tree(
            ctx.runs / job.run_root
        )  # the workspaces of the earlier attempt are large and of no use now (D-450: a folder that cannot be deleted is moved aside)
    job_dir.mkdir(parents=True, exist_ok=True)
    argv = job.argv(ctx)
    if job.kind == "pytest" and not ctx.caps.get("xdist"):
        argv = strip_xdist(argv)
    (job_dir / "command.txt").write_text(" ".join(argv) + "\n", encoding="utf-8")
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "FORGE_BENCH_RUNS": str(ctx.runs),
        "CI": "1",
        "NO_COLOR": "1",
        "npm_config_yes": "true",
        "PYTHON_MANAGER_AUTOMATIC_INSTALL": "0",  # the Python install manager must never ask to install anything during an unattended night
        "FORGE_ENV_FILE": ctx.env_file,
        **job.env,
    }
    if not ctx.env_file or not job.uses_env_file:
        env.pop("FORGE_ENV_FILE", None)
    env = without_store_aliases(env)  # a bare `python3` must fail at once, not open the Microsoft Store
    if job.kind == "pytest":
        env.pop("CI", None)  # CI changes how some tools behave; the tests are written for a person's machine
    limit = min(job.timeout_min * 60, max(60, deadline - time.time()))
    stall = job.stall_min * 60
    watch = [ctx.runs / job.run_root] if job.run_root else []
    console = job_dir / "console.log"
    started = time.time()
    entry.update(status="RUNNING", started_at=time.strftime("%Y-%m-%d %H:%M:%S"))
    save()
    log(f"START {job.id}: {job.title} (limit {int(limit / 60)} min)")
    handle = console.open("w", encoding="utf-8", errors="replace")
    kwargs: dict[str, Any] = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if sys.platform == "win32"
        else {"start_new_session": True}
    )
    process = subprocess.Popen(
        argv, cwd=REPO, env=env, stdout=handle, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, **kwargs
    )
    marker = activity(watch, console)
    last_change = time.time()
    ended = "done"
    while process.poll() is None:
        try:
            time.sleep(POLL_S)
        except KeyboardInterrupt:  # Ctrl+C in the run window: the job has its own process group and would go on alone, so stop it too
            kill_tree(process)
            raise
        keep_awake()
        now = time.time()
        (ctx.out / "HEARTBEAT.txt").write_text(
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} running {job.id} for {int(now - started)} s\n",
            encoding="utf-8",
        )
        current = activity(watch, console)
        if current != marker:
            marker, last_change = current, now
        if (ctx.out / STOP_NOW).exists():
            ended = "INTERRUPTED"
        elif now - started > limit:
            ended = "TIMEOUT"
        elif now - last_change > stall:
            ended = "STALLED"
        if ended != "done":
            log(f"STOP {job.id}: {ended}")
            kill_tree(process)
            with contextlib.suppress(Exception):
                process.wait(timeout=30)
            break
    handle.close()
    seconds = time.time() - started
    code = process.returncode
    status, finding, details = analyse(job, code, ended, job_dir, ctx)
    evidence = collect_evidence(job, job_dir, ctx)
    if status not in ("PASS", "INTERRUPTED"):
        write_failure(job, status, finding, details, code, seconds, argv, job_dir, ctx, evidence)
    entry.update(status=status, seconds=round(seconds), finding=finding, evidence=evidence, exit_code=code)
    save()
    log(f"END   {job.id}: {status} in {int(seconds)} s: {finding}")


# --- the night -----------------------------------------------------------------------------------------------------------------


def make_bundle(out: Path) -> None:
    target = out / "results-bundle.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(out.rglob("*")):
            relative = path.relative_to(out)
            if (
                not path.is_file()
                or relative.parts[0] == "runs"
                or path.name in {".lock", "results-bundle.zip"}
                or path.stat().st_size > 5_000_000
            ):
                continue
            if path.suffix.lower() in (".md", ".log", ".txt", ".json", ".html"):
                archive.writestr(str(relative), redact(path.read_text(encoding="utf-8", errors="replace")))
            else:
                archive.write(path, str(relative))


def acquire_lock(out: Path) -> bool:
    lock = out / ".lock"
    if lock.exists():
        with contextlib.suppress(Exception):
            pid = int(lock.read_text().strip())
            if pid != os.getpid() and psutil_alive(pid):
                return False
    lock.write_text(str(os.getpid()))
    return True


def psutil_alive(pid: int) -> bool:
    try:
        if sys.platform == "win32":
            done = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, timeout=20
            )
            return str(pid) in done.stdout
        os.kill(pid, 0)
        return True
    except (OSError, subprocess.TimeoutExpired):
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", default="")
    parser.add_argument(
        "--env-file", default=os.environ.get("FORGE_ENV_FILE", str(Path.home() / ".forge" / ".env"))
    )
    parser.add_argument("--profile", choices=["core", "extended"], default="core")
    parser.add_argument("--max-hours", type=float, default=11.0)
    parser.add_argument("--only", default="")
    parser.add_argument("--skip", default="")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument(
        "--retry",
        action="store_true",
        help="in a folder that already has results: run again every job that did not PASS (failed, problems, timeout, stalled, skipped)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    out = Path(args.out) if args.out else REPO / "overnight-results" / time.strftime("%Y%m%d-%H%M")
    if args.out == "latest":  # Resume-Overnight.cmd: the newest run folder that has a state file
        folders = sorted(
            (p for p in (REPO / "overnight-results").glob("*") if (p / "state.json").is_file()),
            key=lambda p: p.stat().st_mtime,
        )
        if not folders:
            print(
                "There is no earlier run to resume in overnight-results. Start a new one with Start-Overnight.cmd."
            )
            return 2
        out = folders[-1]
        print(f"Resuming {out}")
    ctx = Ctx(repo=REPO, out=out, env_file=args.env_file)
    wanted = {part for part in args.only.split(",") if part}
    skipped_ids = {part for part in args.skip.split(",") if part}
    selected = [
        job
        for job in catalogue()
        if job.tier <= (2 if args.profile == "extended" else 1)
        and (not wanted or job.id in wanted)
        and job.id not in skipped_ids
    ]
    if args.dry_run:
        total = sum(job.est_min for job in selected)
        for job in selected:
            print(
                f"{job.id:22} est {job.est_min:3} min, limit {job.timeout_min:3} min, needs {','.join(job.needs) or '-'}: {job.title}"
            )
        print(
            f"\n{len(selected)} jobs, about {total / 60:.1f} hours if nothing is skipped; budget {args.max_hours} h"
        )
        return 0
    out.mkdir(parents=True, exist_ok=True)
    if not acquire_lock(out):
        log("another overnight run is using this folder; stop it first or choose another --out")
        return 2
    keep_awake()
    for name in (STOP_AFTER_JOB, STOP_NOW):  # a pause asked for in the last session ends when this one starts
        with contextlib.suppress(OSError):
            (out / name).unlink()
    state_file = out / "state.json"
    state: dict[str, Any] = {
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "profile": args.profile,
        "finished": False,
        "jobs": [],
    }
    if state_file.is_file() and not args.no_resume:
        with contextlib.suppress(Exception):
            state = json.loads(state_file.read_text(encoding="utf-8"))
            state["finished"] = False
    previous = {job["id"]: job for job in state.get("jobs", [])}
    entries: list[dict[str, Any]] = []
    for job in [None, *selected]:  # the preflight is the first entry of every night
        job_id, title, group = (
            ("preflight", "Preflight: tools, models, image generation, doctor", "preflight")
            if job is None
            else (job.id, job.title, job.group)
        )
        old = previous.get(job_id)
        entries.append(
            old
            if old and old.get("status") in ({"PASS"} if args.retry else DONE)
            else {
                "id": job_id,
                "title": title,
                "group": group,
                "status": "PENDING",
                "seconds": 0,
                "finding": "",
                "evidence": [],
            }
        )
    state["jobs"] = entries
    code, commit = run_quiet(["git", "rev-parse", "--short", "HEAD"], 20)
    state["commit"] = commit.strip() if code == 0 else "unknown (not a git checkout)"

    def save() -> None:
        state_file.write_text(json.dumps(state, indent=1), encoding="utf-8")
        write_report(out, state)

    deadline = time.time() + args.max_hours * 3600
    save()
    try:
        pre = entries[0]
        caps_file = out / "preflight.json"
        if pre["status"] in DONE and caps_file.is_file() and not args.retry:
            ctx.caps = json.loads(caps_file.read_text(encoding="utf-8")).get("caps", {})
        else:
            pre.update(status="RUNNING")
            save()
            started = time.time()
            try:
                ctx.caps, environment = preflight(ctx)
                state["environment"] = environment
                pre.update(
                    status="PASS",
                    seconds=round(time.time() - started),
                    finding="capabilities: " + ", ".join(k for k, v in ctx.caps.items() if v),
                )
            except Exception as error:  # a broken preflight must not stop the night: assume the basics
                ctx.caps = {"pytest": True, "azure": True}
                pre.update(
                    status="PROBLEMS",
                    seconds=round(time.time() - started),
                    finding=f"preflight crashed ({type(error).__name__}: {error}); assuming Azure only",
                )
            save()
        for job, entry in zip(selected, entries[1:], strict=True):
            if entry["status"] in DONE:
                continue
            if (out / STOP_AFTER_JOB).exists() or (out / STOP_NOW).exists():
                state["paused"] = True
                log(
                    "paused on request: the report so far is saved; double-click Resume-Overnight.cmd to continue"
                )
                break
            missing = [need for need in job.needs if not ctx.caps.get(need)]
            remaining = deadline - time.time()
            if missing:
                entry.update(
                    status="SKIPPED",
                    finding="needs "
                    + ", ".join(missing)
                    + ", which the preflight did not find (see the Environment section)",
                )
            elif remaining < min(job.est_min, job.timeout_min) * 60 * 0.6:
                entry.update(
                    status="SKIPPED",
                    finding=f"not enough of the {args.max_hours} h budget left ({int(remaining / 60)} min)",
                )
            else:
                try:
                    run_job(job, ctx, deadline, entry, save)
                except Exception as error:  # the runner's own bug on one job must not end the night
                    entry.update(status="FAILED", finding=f"runner error: {type(error).__name__}: {error}")
                    log(f"runner error in {job.id}: {error}")
                if entry["status"] == "INTERRUPTED":
                    state["paused"] = True
                    save()
                    break
            save()
    except KeyboardInterrupt:
        log("interrupted: the report so far is saved; run again with the same --out to continue")
    finally:
        for entry in entries:
            if (
                entry["status"] == "RUNNING"
            ):  # Ctrl+C or a shutdown while a job ran: it is run again from its start on resume
                entry["status"] = "INTERRUPTED"
                entry["finding"] = (
                    "the run was cut short while this job was running; it runs again when you resume"
                )
        state["finished"] = all(entry["status"] not in ("PENDING", "INTERRUPTED") for entry in entries)
        save()
        with contextlib.suppress(Exception):
            make_bundle(out)
        with contextlib.suppress(OSError):
            (out / ".lock").unlink()
    log(f"done: open {out / 'MORNING_REPORT.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
