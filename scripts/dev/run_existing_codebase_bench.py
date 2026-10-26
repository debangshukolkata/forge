"""Existing-codebase benchmark (TODO C22): ten challenges on two downloaded, pinned repositories. Never calls the model.

    python scripts/dev/run_existing_codebase_bench.py list
    python scripts/dev/run_existing_codebase_bench.py prepare E02 [--run-name try1]
    python scripts/dev/run_existing_codebase_bench.py evaluate E02 --run-dir C:\\Work\\ForgeRuns\\existing\\try1\\E02 [--seconds N --cost USD]
    python scripts/dev/run_existing_codebase_bench.py selftest [E02 ...]     (proves each check fails before and passes on a known solution)

`prepare` copies the pinned clone (never modified) into <run-dir>/repo, applies the seeded bug if the challenge has one, snapshots the files,
runs the baseline checks and prints the exact Forge commands for the live step (same environment variables and driver as
scripts/benchmark/run_challenges.py: `forge new --repo ...` then scripts/campaign/drive_forge.py). `evaluate` looks at the delivered
repository (default <run-dir>/workspace/repo), runs the pass check, the repo's own suite, the mutation check if the challenge has one,
and writes <run-dir>/result.json. Details and scoring: docs/CODE_BENCHMARK_EXISTING.md."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from existing_bench import harness as H
from existing_bench.challenges import APPROVAL, BY_ID, CHALLENGES

FORGE_REPO = Path(__file__).resolve().parents[2]
REPOS_ROOT = Path(os.environ.get("FORGE_BENCH_REPOS", r"C:\Work\Projects\Forge-benchmark-repos"))
RUNS = Path(os.environ.get("FORGE_BENCH_RUNS", r"C:\Work\ForgeRuns")) / "existing"


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")


def python_for(challenge: H.Challenge, args: argparse.Namespace) -> str:
    if challenge.repo == "click":
        return args.python or H.default_python("click")
    return args.template_python or args.python or H.default_python("fastapi-template")


def prepare(
    challenge: H.Challenge, run_dir: Path, python: str, repos_root: Path = REPOS_ROOT
) -> dict[str, Any]:
    repo_copy = run_dir / "repo"
    run_dir.mkdir(parents=True, exist_ok=True)
    H.copy_repo(repos_root / challenge.repo, repo_copy)
    H.apply_edits(repo_copy, challenge.seeded)
    write_json(run_dir / "manifest.json", H.snapshot(repo_copy))
    (run_dir / "prompt.txt").write_text(challenge.brief + APPROVAL, encoding="utf-8")
    baseline: dict[str, Any] = {"check": H.run_check_file(challenge, repo_copy, python)}
    if challenge.run_existing_suite:
        baseline["existing_suite"] = H.run_existing_suite(challenge, repo_copy, python)
    mypy = H.mypy_error_count(python, repo_copy, challenge.mypy_paths)
    if mypy is not None:
        baseline["mypy_errors"] = mypy
    # A check that already passes before any work proves nothing.
    baseline["check_fails_before_work"] = baseline["check"]["status"] in ("fail", "none", "skipped")
    write_json(run_dir / "baseline.json", baseline)
    return baseline


def evaluate(
    challenge: H.Challenge, run_dir: Path, delivered: Path, python: str, args: argparse.Namespace
) -> dict[str, Any]:
    pristine = run_dir / "repo"
    before = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    changes = H.diff_snapshots(before, H.snapshot(delivered))
    baseline_file = run_dir / "baseline.json"
    baseline = json.loads(baseline_file.read_text(encoding="utf-8")) if baseline_file.exists() else {}
    result: dict[str, Any] = {
        "id": challenge.id,
        "title": challenge.title,
        "tier": challenge.tier,
        "delivered_repo": str(delivered),
    }
    result["changed_files"] = changes
    result["new_tests_added"] = H.tests_added(pristine, delivered, changes)
    result["check"] = H.run_check_file(challenge, delivered, python)
    result["existing_tests"] = H.run_existing_suite(challenge, delivered, python)
    if challenge.mutants:
        result["mutation"] = H.run_mutation_check(
            challenge, delivered, changes, python, Path(tempfile.mkdtemp(prefix="bench-mut-"))
        )
    if challenge.mypy_paths:
        after = H.mypy_error_count(python, delivered, challenge.mypy_paths)
        result["mypy_errors"] = {"before": baseline.get("mypy_errors"), "after": after}
    touched = (
        result["changed_files"]["added"]
        + result["changed_files"]["modified"]
        + result["changed_files"]["deleted"]
    )
    result["expected_files_changed"] = [
        f for f in challenge.expected_files if any(t == f or t.startswith(f + "/") for t in touched)
    ]
    source_touched = [t for t in touched if t.startswith(("src/", "backend/app/")) and not H.is_test_file(t)]
    result["source_files_changed"] = source_touched
    events = H.read_events(delivered.parent / ".forge" / "transcripts" / "events.jsonl")
    nav = H.navigation(events, challenge.expected_files)
    result["navigation"] = nav
    result["seconds"] = (
        args.seconds if args.seconds is not None else H.seconds_between(nav["first_event"], nav["last_event"])
    )
    result["cost_usd"] = args.cost
    result["where_lost"] = args.where_lost or ""
    reasons: list[str] = []
    if result["check"]["status"] == "fail":
        reasons.append("pass check failed")
    if result["existing_tests"]["status"] == "fail":
        reasons.append("existing tests broke")
    if challenge.require_new_tests and result["new_tests_added"] < 1:
        reasons.append("no new tests")
    if challenge.forbid_source_changes and source_touched:
        reasons.append("source files were changed")
    if "mutation" in result and result["mutation"]["status"] != "pass":
        reasons.append(f"tests caught {result['mutation']['killed']}/{result['mutation']['total']} mutants")
    mypy = result.get("mypy_errors")
    if mypy and mypy["after"] is not None and mypy["before"] is not None and mypy["after"] > mypy["before"]:
        reasons.append("mypy reports more errors")
    skipped = result["check"]["status"] == "skipped"
    result["passed"] = None if skipped and not reasons else not reasons
    result["fail_reasons"] = reasons + (
        ["pass check skipped: " + result["check"]["reason"]] if skipped else []
    )
    write_json(run_dir / "result.json", result)
    return result


def summary_line(result: dict[str, Any]) -> str:
    nav = result["navigation"]
    cost = "n/a" if result["cost_usd"] is None else f"${result['cost_usd']}"
    verdict = {True: "PASS", False: "FAIL", None: "NOT CHECKED"}[result["passed"]]
    return (
        f"{result['id']} {verdict}: check={result['check']['status']} existing={result['existing_tests']['status']} "
        f"new_tests={result['new_tests_added']} files_found={nav['right_files_found']} "
        f"changed={len(result['changed_files']['added']) + len(result['changed_files']['modified'])} time={result['seconds']}s cost={cost}"
        + (f" ({'; '.join(result['fail_reasons'])})" if result["fail_reasons"] else "")
    )


def selftest(challenge: H.Challenge, python: str, repos_root: Path = REPOS_ROOT) -> dict[str, Any]:
    """Prepare, then apply the known solution and evaluate: the check must fail first and pass afterwards."""
    if not challenge.reference and not challenge.reference_files:
        return {"id": challenge.id, "status": "no reference solution"}
    work = Path(tempfile.mkdtemp(prefix=f"bench-self-{challenge.id}-"))
    try:
        baseline = prepare(challenge, work, python, repos_root)
        delivered = work / "delivered"
        shutil.copytree(work / "repo", delivered)
        H.apply_edits(delivered, challenge.reference)
        H.write_files(delivered, challenge.reference_files)
        namespace = argparse.Namespace(seconds=0, cost=None, where_lost="")
        result = evaluate(challenge, work, delivered, python, namespace)
        fails_first = baseline["check_fails_before_work"] or challenge.check is None
        return {
            "id": challenge.id,
            "status": "ok" if fails_first and result["passed"] else "PROBLEM",
            "fails_first": fails_first,
            "passes_after": result["passed"],
            "reasons": result["fail_reasons"],
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["list", "prepare", "evaluate", "selftest"])
    parser.add_argument("ids", nargs="*")
    parser.add_argument("--run-name", default=time.strftime("existing-%Y%m%d-%H%M"))
    parser.add_argument("--run-dir", type=Path, help="evaluate: the folder prepare created")
    parser.add_argument(
        "--delivered", type=Path, help="evaluate: the repository to score (default <run-dir>/workspace/repo)"
    )
    parser.add_argument("--python", help="interpreter for the checks (click: .venv-click; needs pytest<9)")
    parser.add_argument(
        "--template-python",
        help="interpreter with the template's backend dependencies (Python 3.14 per its pyproject)",
    )
    parser.add_argument(
        "--seconds", type=int, help="wall time of the live run, if the event log is not enough"
    )
    parser.add_argument("--cost", type=float, help="cost in USD from the run's cost counter")
    parser.add_argument("--where-lost", help="your note on where it lost time")
    args = parser.parse_args(argv)

    unknown = [i for i in args.ids if i.upper() not in BY_ID]
    if unknown:
        print(f"unknown challenge id: {', '.join(unknown)}")
        return 2
    selected = [BY_ID[i.upper()] for i in args.ids] if args.ids else list(CHALLENGES)
    if args.command == "list":
        for c in CHALLENGES:
            print(f"{c.id}  {c.repo:17} {c.tier:24} {c.title}")
        return 0
    if args.command == "selftest":
        worst = 0
        for c in selected:
            outcome = selftest(c, python_for(c, args))
            print(json.dumps(outcome))
            worst = max(worst, 0 if outcome["status"] in ("ok", "no reference solution") else 1)
        return worst
    if len(selected) != 1:
        print(f"{args.command} takes exactly one challenge id")
        return 2
    challenge = selected[0]
    python = python_for(challenge, args)
    if args.command == "prepare":
        run_dir = RUNS / args.run_name / challenge.id
        baseline = prepare(challenge, run_dir, python)
        print(
            f"Prepared {challenge.id} ({challenge.title}) in {run_dir}\nBaseline: {json.dumps({k: (v['status'] if isinstance(v, dict) else v) for k, v in baseline.items()})}"
        )
        if not baseline["check_fails_before_work"]:
            print(
                "WARNING: the pass check already passes before any work; do not use this challenge until that is fixed."
            )
        print(
            "\nLive step (spends Azure tokens; needs the user's OK). Run in PowerShell from the Forge repo:\n"
        )
        print("\n".join(H.forge_commands(challenge, run_dir, FORGE_REPO, run_dir / "repo")))
        return 0
    run_dir = args.run_dir
    if run_dir is None or not (run_dir / "manifest.json").exists():
        print("evaluate needs --run-dir pointing at a folder made by prepare")
        return 2
    delivered = args.delivered or run_dir / "workspace" / "repo"
    if not delivered.is_dir():
        print(f"delivered repository not found: {delivered}")
        return 2
    result = evaluate(challenge, run_dir, delivered, python, args)
    print(summary_line(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
