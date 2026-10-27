"""Helpers for the existing-codebase benchmark: copy a pinned repository, apply a seeded patch, run the model-independent checks, compare the result.

Nothing here calls the model or runs Forge. The pinned clones are only read."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CHECKS_DIR = Path(__file__).resolve().parent / "checks"
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".forge",
    ".venv",
    "venv",
}
# One click test fails on the build machine before anybody touches the code (UnicodeDecodeError on Windows).
KNOWN_BASELINE_FAILURES = {
    "click": {"tests/test_utils.py::test_filename_formatting"},
    "fastapi-template": set(),
}
TEMPLATE_ENV = {
    "SECRET_KEY": "bench-secret-not-the-default-value",  # check_secrets: fake
    "PROJECT_NAME": "Bench",
    "DATABASE_URL": "postgresql://bench:bench-pass-123@localhost:5432/bench",  # check_secrets: fake
    "FIRST_SUPERUSER": "admin@example.com",
    "FIRST_SUPERUSER_PASSWORD": "bench-admin-pass-123",  # check_secrets: fake
    "FASTAPI_ENV": "development",
}
READ_TOOLS = {"read_file", "grep", "glob", "list_dir", "search_files", "lsp_symbols"}
EDIT_TOOLS = {"write_file", "edit_file", "multi_edit", "delete_file", "move_file"}


class BenchError(Exception):
    """A problem with the benchmark setup itself (not a model failure)."""


@dataclass(frozen=True)
class Edit:
    """One exact text replacement in one file; `old` must occur exactly once."""

    path: str
    old: str
    new: str


@dataclass(frozen=True)
class Challenge:
    id: str
    repo: str  # folder name under the repos root: click or fastapi-template
    title: str
    tier: str
    brief: str  # the prompt the model gets: no file names unless a real user would give them
    expected_files: tuple[
        str, ...
    ]  # files a correct change touches or must read (paths relative to the repo root)
    check: str | None  # pytest file under checks/ that must pass after the work and fail before it
    app_folder: str = "."
    seeded: tuple[Edit, ...] = ()
    mutants: tuple[Edit, ...] = ()  # for "write the missing tests": source mutations the new tests must catch
    min_killed: int = 0
    require_new_tests: bool = False
    forbid_source_changes: bool = False
    run_existing_suite: bool = True  # click: yes; the template suite needs Postgres, so it is opt-in
    mypy_paths: tuple[str, ...] = ()  # files that must not get more mypy errors (template type pass)
    reference: tuple[Edit, ...] = ()  # a known solution, used by `selftest` to prove the check can pass
    reference_files: dict[str, str] = field(default_factory=dict)
    needs_template_python: bool = False


# ---------------------------------------------------------------- copying and patching


def copy_repo(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise BenchError(f"pinned clone not found: {source}")
    if destination.exists():
        raise BenchError(f"destination already exists: {destination}")
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns(*SKIP_DIRS))


def apply_edits(root: Path, edits: tuple[Edit, ...]) -> list[str]:
    """Apply exact replacements, keeping each file's bytes (line endings, BOM) as they were."""
    touched: list[str] = []
    for edit in edits:
        target = root / edit.path
        if not target.is_file():
            raise BenchError(f"edit target missing: {edit.path}")
        raw = target.read_bytes()
        text = raw.decode("utf-8")
        crlf = "\r\n" in text
        old = edit.old.replace("\n", "\r\n") if crlf else edit.old
        new = edit.new.replace("\n", "\r\n") if crlf else edit.new
        if text.count(old) != 1:
            raise BenchError(
                f"{edit.path}: expected exactly one match, found {text.count(old)}: {edit.old[:60]!r}"
            )
        target.write_bytes(text.replace(old, new).encode("utf-8"))
        touched.append(edit.path)
    return touched


def write_files(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- snapshots


def snapshot(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for directory, subdirectories, filenames in os.walk(root):
        subdirectories[:] = [d for d in subdirectories if d not in SKIP_DIRS]
        for name in filenames:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            hashes[relative] = hashlib.sha1(path.read_bytes()).hexdigest()
    return hashes


def diff_snapshots(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    return {
        "added": sorted(set(after) - set(before)),
        "modified": sorted(p for p in before if p in after and before[p] != after[p]),
        "deleted": sorted(set(before) - set(after)),
    }


def is_test_file(relative: str) -> bool:
    parts = relative.replace("\\", "/").split("/")
    name = parts[-1]
    return relative.endswith(".py") and (
        "tests" in parts[:-1] or name.startswith("test_") or name.endswith("_test.py")
    )


def count_test_functions(path: Path) -> int:
    if not path.is_file():
        return 0
    return len(
        re.findall(r"^\s*(?:async\s+)?def test_", path.read_text(encoding="utf-8", errors="replace"), re.M)
    )


def tests_added(pristine: Path, delivered: Path, changes: dict[str, list[str]]) -> int:
    total = 0
    for relative in changes["added"] + changes["modified"]:
        if is_test_file(relative):
            total += max(
                0, count_test_functions(delivered / relative) - count_test_functions(pristine / relative)
            )
    return total


# ---------------------------------------------------------------- running pytest and friends


def with_unix_tools(path: str) -> str:
    """click's pager tests run the real `cat`; a plain PowerShell has none on PATH (Git for Windows ships one), which made a correct delivery look broken."""
    if shutil.which("cat", path=path):
        return path
    for folder in (r"C:\Program Files\Git\usr\bin", r"C:\Program Files (x86)\Git\usr\bin"):
        if (Path(folder) / "cat.exe").is_file():
            return path + os.pathsep + folder
    return path


def check_environment(challenge: Challenge, repo: Path) -> tuple[dict[str, str], Path]:
    """Environment variables and working directory for running Python against the repo copy."""
    env = {**os.environ, "BENCH_REPO": str(repo), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    if challenge.repo == "click":
        env["PYTHONPATH"] = str(repo / "src")
        env["PATH"] = with_unix_tools(env.get("PATH", ""))
        return env, repo
    env.update({key: env.get(key) or value for key, value in TEMPLATE_ENV.items()})
    env["PYTHONPATH"] = str(repo / "backend")
    return env, repo / "backend"


def parse_pytest(output: str) -> dict[str, Any]:
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}
    summary = [
        line
        for line in output.splitlines()
        if re.search(r"\b(passed|failed|error|errors|skipped)\b", line) and " in " in line
    ]
    if summary:
        for number, word in re.findall(r"(\d+) (passed|failed|errors?|skipped)", summary[-1]):
            counts["errors" if word.startswith("error") else word] = int(number)
    failed = sorted(set(re.findall(r"^(?:FAILED|ERROR) (\S+?)(?: - |$)", output, re.M)))
    return {**counts, "failed_ids": failed}


def run_pytest(
    python: str, args: list[str], cwd: Path, env: dict[str, str], timeout: int = 1500
) -> dict[str, Any]:
    try:
        process = subprocess.run(
            [python, "-m", "pytest", *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return {
            "returncode": -1,
            "timed_out": True,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "skipped": 0,
            "failed_ids": [],
            "tail": "",
        }
    output = process.stdout + process.stderr
    result = parse_pytest(output)
    result.update({"returncode": process.returncode, "timed_out": False, "tail": output[-1500:]})
    return result


def run_check_file(challenge: Challenge, repo: Path, python: str) -> dict[str, Any]:
    """The model-independent pass check. 'skipped' when the interpreter lacks the template's dependencies."""
    if challenge.check is None:
        return {"status": "none"}
    env, cwd = check_environment(challenge, repo)
    if (
        challenge.needs_template_python
        and subprocess.run([python, "-c", "import fastapi, sqlmodel"], capture_output=True).returncode != 0
    ):
        return {
            "status": "skipped",
            "reason": "the check interpreter lacks fastapi/sqlmodel: pass --template-python",
        }
    result = run_pytest(
        python,
        [
            "-c",
            str(CHECKS_DIR / "pytest.ini"),
            "--rootdir",
            str(CHECKS_DIR),
            str(CHECKS_DIR / challenge.check),
            "-q",
            "-rf",
        ],
        cwd,
        env,
    )
    status = "pass" if result["returncode"] == 0 else "fail"
    return {"status": status, **{k: result[k] for k in ("passed", "failed", "errors", "failed_ids", "tail")}}


def run_existing_suite(challenge: Challenge, repo: Path, python: str) -> dict[str, Any]:
    """The repo's own tests; failures that were already there on the pinned commit are reported apart."""
    if not challenge.run_existing_suite:
        return {
            "status": "not run",
            "reason": "needs Postgres: run it yourself with --existing-suite and DATABASE_URL set",
        }
    env, cwd = check_environment(challenge, repo)
    result = run_pytest(python, ["tests", "-q", "-rf", "-p", "no:cacheprovider"], cwd, env)
    known = KNOWN_BASELINE_FAILURES.get(challenge.repo, set())
    new_failures = [f for f in result["failed_ids"] if f not in known]
    broken = result["timed_out"] or (result["returncode"] != 0 and not result["failed_ids"])
    return {
        "status": "pass" if not new_failures and not broken else "fail",
        "passed": result["passed"],
        "failed": result["failed"],
        "errors": result["errors"],
        "known_baseline_failures_seen": [f for f in result["failed_ids"] if f in known],
        "new_failures": new_failures,
        "tail": result["tail"] if new_failures or broken else "",
    }


def mypy_error_count(python: str, repo: Path, paths: tuple[str, ...]) -> int | None:
    if not paths:
        return None
    if subprocess.run([python, "-m", "mypy", "--version"], capture_output=True).returncode != 0:
        return None
    process = subprocess.run(
        [python, "-m", "mypy", *paths], cwd=repo / "backend", capture_output=True, text=True, errors="replace",
        env={**os.environ, **TEMPLATE_ENV, "PYTHONPATH": str(repo / "backend")},
    )  # fmt: skip
    return len(re.findall(r": error:", process.stdout))


def run_mutation_check(
    challenge: Challenge, repo: Path, changes: dict[str, list[str]], python: str, work: Path
) -> dict[str, Any]:
    """Do the delivered new tests fail when the source is broken in known ways?"""
    new_tests = [p for p in changes["added"] + changes["modified"] if is_test_file(p)]
    if not new_tests:
        return {
            "status": "fail",
            "reason": "no test file was added or changed",
            "killed": 0,
            "total": len(challenge.mutants),
        }
    env, _ = check_environment(challenge, repo)
    baseline = run_pytest(python, [*new_tests, "-q", "-p", "no:cacheprovider"], repo, env)
    if baseline["returncode"] != 0:
        return {
            "status": "fail",
            "reason": "the delivered tests fail on the unchanged source",
            "killed": 0,
            "total": len(challenge.mutants),
            "tail": baseline["tail"],
        }
    killed = 0
    survivors: list[str] = []
    for index, mutant in enumerate(challenge.mutants):
        copy = work / f"mutant{index}"
        shutil.rmtree(copy, ignore_errors=True)
        shutil.copytree(repo, copy, ignore=shutil.ignore_patterns(*SKIP_DIRS))
        apply_edits(copy, (mutant,))
        mutant_env, _ = check_environment(challenge, copy)
        result = run_pytest(python, [*new_tests, "-q", "-p", "no:cacheprovider"], copy, mutant_env)
        if result["returncode"] != 0:
            killed += 1
        else:
            survivors.append(f"{mutant.path}: {mutant.old.strip()[:70]}")
        shutil.rmtree(copy, ignore_errors=True)
    return {
        "status": "pass" if killed >= challenge.min_killed else "fail",
        "killed": killed,
        "total": len(challenge.mutants),
        "survivors": survivors,
    }


# ---------------------------------------------------------------- reading the run


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    return events


def navigation(events: list[dict[str, Any]], expected: tuple[str, ...]) -> dict[str, Any]:
    """Which expected files the model looked at (on-demand search), and how much it wandered before the first one."""
    calls: list[tuple[str, str]] = []
    failed = 0
    for event in events:
        payload = event.get("payload") or {}
        if event.get("type") == "tool_call_started":
            calls.append(
                (
                    str(payload.get("name")),
                    json.dumps(payload.get("arguments") or {}) + str(payload.get("summary") or ""),
                )
            )
        elif event.get("type") == "tool_call_finished" and not payload.get("ok", True):
            failed += 1
    normalised = [(name, text.replace("\\\\", "/").replace("\\", "/")) for name, text in calls]
    found = [
        f
        for f in expected
        if any(
            f in text or Path(f).name in text
            for name, text in normalised
            if name in READ_TOOLS | EDIT_TOOLS | {"run_command"}
        )
    ]
    first_hit = next(
        (i for i, (_, text) in enumerate(normalised) if any(Path(f).name in text for f in expected)), None
    )
    first_edit = next((i for i, (name, _) in enumerate(normalised) if name in EDIT_TOOLS), None)
    stamps = [str(e.get("ts", "")) for e in events if e.get("ts")]
    return {
        "expected_files_looked_at": found,
        "right_files_found": f"{len(found)}/{len(expected)}",
        "tool_calls": len(calls),
        "failed_tool_calls": failed,
        "calls_before_first_expected_file": first_hit,
        "calls_before_first_edit": first_edit,
        "first_event": stamps[0] if stamps else None,
        "last_event": stamps[-1] if stamps else None,
    }


def seconds_between(first: str | None, last: str | None) -> int | None:
    from datetime import datetime

    if not first or not last:
        return None
    try:
        return round((datetime.fromisoformat(last) - datetime.fromisoformat(first)).total_seconds())
    except ValueError:
        return None


def forge_commands(challenge: Challenge, run_dir: Path, forge_repo: Path, repo_copy: Path) -> list[str]:
    """The exact commands for the live step, with the same environment variables run_challenges.py sets."""
    workspace = run_dir / "workspace"
    python = forge_repo / ".venv" / "Scripts" / "python"
    return [
        f'$env:FORGE_HOME = "{run_dir / "home"}"',
        f'$env:FORGE_ENV_FILE = "{forge_repo / ".env"}"',
        '$env:PYTHONIOENCODING = "utf-8"',
        f'& "{python}" -m forge.cli new --repo "{repo_copy}" --project existing-{challenge.id.lower()} --workspace "{workspace}" --app-folder "{challenge.app_folder}"',
        f'& "{python}" "{forge_repo / "scripts" / "campaign" / "drive_forge.py"}" "{workspace}" "{run_dir / "prompt.txt"}" "{run_dir / "run.json"}"',
        f'& "{python}" "{forge_repo / "scripts" / "dev" / "run_existing_codebase_bench.py"}" evaluate {challenge.id} --run-dir "{run_dir}"',
    ]


def default_python(name: str) -> str:
    candidate = (
        Path(os.environ.get("FORGE_BENCH_REPOS", r"C:\Work\Projects\Forge-benchmark-repos"))
        / f".venv-{name}"
        / "Scripts"
        / "python.exe"
    )
    return str(candidate) if candidate.exists() else sys.executable
