"""Deterministic tests of the existing-codebase benchmark helpers (TODO C22). No model, no network; the clones are only read."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "dev"))
import run_existing_codebase_bench as runner
from existing_bench import harness as H
from existing_bench.challenges import BY_ID, CHALLENGES

CLONES = Path(runner.REPOS_ROOT)


def test_registry_has_ten_challenges_split_six_and_four() -> None:
    assert len(CHALLENGES) == 10
    assert len({c.id for c in CHALLENGES}) == 10
    assert sum(c.repo == "click" for c in CHALLENGES) == 6
    assert sum(c.repo == "fastapi-template" for c in CHALLENGES) == 4


def test_every_challenge_has_a_brief_a_check_and_expected_files() -> None:
    for challenge in CHALLENGES:
        assert challenge.brief.strip() and challenge.expected_files
        assert challenge.check is not None or challenge.mutants
        if challenge.check:
            assert (H.CHECKS_DIR / challenge.check).is_file(), challenge.id
        if challenge.mutants:
            assert 0 < challenge.min_killed <= len(challenge.mutants)


def test_brief_does_not_leak_the_solution_files_for_the_vague_one() -> None:
    brief = BY_ID["T04"].brief
    assert "crud" not in brief and "login" not in brief and "lower" not in brief


def test_apply_edits_replaces_exactly_one_match(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    H.apply_edits(tmp_path, (H.Edit("a.py", "y = 2", "y = 3"),))
    assert (tmp_path / "a.py").read_text(encoding="utf-8") == "x = 1\ny = 3\n"


def test_apply_edits_refuses_zero_or_many_matches(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
    with pytest.raises(H.BenchError):
        H.apply_edits(tmp_path, (H.Edit("a.py", "x = 1", "x = 2"),))
    with pytest.raises(H.BenchError):
        H.apply_edits(tmp_path, (H.Edit("a.py", "nothing", "x"),))
    with pytest.raises(H.BenchError):
        H.apply_edits(tmp_path, (H.Edit("missing.py", "a", "b"),))


def test_apply_edits_keeps_windows_line_endings(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_bytes(b"one\r\ntwo\r\nthree\r\n")
    H.apply_edits(tmp_path, (H.Edit("a.txt", "one\ntwo", "one\n2"),))
    assert (tmp_path / "a.txt").read_bytes() == b"one\r\n2\r\nthree\r\n"


def test_copy_repo_skips_git_and_refuses_to_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "src"
    (source / ".git").mkdir(parents=True)
    (source / ".git" / "HEAD").write_text("ref", encoding="utf-8")
    (source / "pkg").mkdir()
    (source / "pkg" / "m.py").write_text("1", encoding="utf-8")
    destination = tmp_path / "copy"
    H.copy_repo(source, destination)
    assert (destination / "pkg" / "m.py").exists() and not (destination / ".git").exists()
    with pytest.raises(H.BenchError):
        H.copy_repo(source, destination)
    with pytest.raises(H.BenchError):
        H.copy_repo(tmp_path / "nope", tmp_path / "other")


def test_snapshot_diff_reports_added_modified_deleted(tmp_path: Path) -> None:
    (tmp_path / "keep.py").write_text("a", encoding="utf-8")
    (tmp_path / "change.py").write_text("a", encoding="utf-8")
    (tmp_path / "gone.py").write_text("a", encoding="utf-8")
    before = H.snapshot(tmp_path)
    (tmp_path / "change.py").write_text("b", encoding="utf-8")
    (tmp_path / "gone.py").unlink()
    (tmp_path / "new.py").write_text("c", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_text("noise", encoding="utf-8")
    changes = H.diff_snapshots(before, H.snapshot(tmp_path))
    assert changes == {"added": ["new.py"], "modified": ["change.py"], "deleted": ["gone.py"]}


def test_is_test_file_and_counting_new_tests(tmp_path: Path) -> None:
    assert (
        H.is_test_file("tests/test_x.py")
        and H.is_test_file("backend/tests/api/helper.py")
        and H.is_test_file("pkg/test_y.py")
    )
    assert not H.is_test_file("src/click/core.py") and not H.is_test_file("tests/data.json")
    pristine, delivered = tmp_path / "p", tmp_path / "d"
    (pristine / "tests").mkdir(parents=True)
    (delivered / "tests").mkdir(parents=True)
    (pristine / "tests" / "test_a.py").write_text("def test_one():\n    pass\n", encoding="utf-8")
    (delivered / "tests" / "test_a.py").write_text(
        "def test_one():\n    pass\n\nasync def test_two():\n    pass\n", encoding="utf-8"
    )
    (delivered / "tests" / "test_b.py").write_text("def test_three():\n    pass\n", encoding="utf-8")
    changes = {"added": ["tests/test_b.py"], "modified": ["tests/test_a.py"], "deleted": []}
    assert H.tests_added(pristine, delivered, changes) == 2


def test_parse_pytest_counts_and_failed_ids() -> None:
    output = (
        "FAILED tests/test_utils.py::test_filename_formatting - UnicodeDecodeError\n"
        "ERROR tests/test_x.py::test_boom\n"
        "=== 1 failed, 636 passed, 12 skipped, 1 xfailed, 1 error in 21.03s ===\n"
    )
    parsed = H.parse_pytest(output)
    assert (parsed["passed"], parsed["failed"], parsed["skipped"], parsed["errors"]) == (636, 1, 12, 1)
    assert parsed["failed_ids"] == [
        "tests/test_utils.py::test_filename_formatting",
        "tests/test_x.py::test_boom",
    ]


def test_known_baseline_failure_is_not_a_new_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    challenge = BY_ID["E01"]
    known = "tests/test_utils.py::test_filename_formatting"
    assert known in H.KNOWN_BASELINE_FAILURES["click"]

    def fake_run(
        python: str, args: list[str], cwd: Path, env: dict[str, str], timeout: int = 0
    ) -> dict[str, object]:
        return {
            "returncode": 1,
            "timed_out": False,
            "passed": 636,
            "failed": 1,
            "errors": 0,
            "skipped": 12,
            "failed_ids": [known],
            "tail": "",
        }

    monkeypatch.setattr(H, "run_pytest", fake_run)
    outcome = H.run_existing_suite(challenge, tmp_path, "python")
    assert (
        outcome["status"] == "pass"
        and outcome["new_failures"] == []
        and outcome["known_baseline_failures_seen"] == [known]
    )

    def fake_run_new(
        python: str, args: list[str], cwd: Path, env: dict[str, str], timeout: int = 0
    ) -> dict[str, object]:
        return {
            "returncode": 1,
            "timed_out": False,
            "passed": 635,
            "failed": 2,
            "errors": 0,
            "skipped": 12,
            "failed_ids": [known, "tests/test_types.py::test_bool"],
            "tail": "x",
        }

    monkeypatch.setattr(H, "run_pytest", fake_run_new)
    outcome = H.run_existing_suite(challenge, tmp_path, "python")
    assert outcome["status"] == "fail" and outcome["new_failures"] == ["tests/test_types.py::test_bool"]


def test_template_suite_is_not_run_without_postgres(tmp_path: Path) -> None:
    assert H.run_existing_suite(BY_ID["T01"], tmp_path, "python")["status"] == "not run"


def test_navigation_finds_expected_files_and_counts_wandering() -> None:
    events = [
        {
            "type": "tool_call_started",
            "ts": "2026-10-27T10:00:00",
            "payload": {"name": "grep", "arguments": {"pattern": "x", "path": "src"}, "summary": "grep x"},
        },
        {"type": "tool_call_finished", "payload": {"ok": False}},
        {
            "type": "tool_call_started",
            "ts": "2026-10-27T10:00:30",
            "payload": {
                "name": "read_file",
                "arguments": {"path": "src\\click\\types.py"},
                "summary": "read",
            },
        },
        {
            "type": "tool_call_started",
            "ts": "2026-10-27T10:01:30",
            "payload": {"name": "edit_file", "arguments": {"path": "src/click/types.py"}, "summary": "edit"},
        },
    ]
    nav = H.navigation(events, ("src/click/types.py", "CHANGES.rst"))
    assert nav["right_files_found"] == "1/2" and nav["calls_before_first_expected_file"] == 1
    assert nav["calls_before_first_edit"] == 2 and nav["failed_tool_calls"] == 1 and nav["tool_calls"] == 3
    assert H.seconds_between(nav["first_event"], nav["last_event"]) == 90


def test_read_events_ignores_broken_lines(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text('{"type": "a"}\nnot json\n{"type": "b"}\n', encoding="utf-8")
    assert [e["type"] for e in H.read_events(path)] == ["a", "b"]
    assert H.read_events(tmp_path / "missing.jsonl") == []


def test_forge_commands_use_the_run_challenges_flags(tmp_path: Path) -> None:
    commands = "\n".join(
        H.forge_commands(BY_ID["T01"], tmp_path / "run", Path("C:/Forge"), tmp_path / "run" / "repo")
    )
    for fragment in (
        "FORGE_HOME",
        "FORGE_ENV_FILE",
        "PYTHONIOENCODING",
        "-m forge.cli new --repo",
        "--workspace",
        '--app-folder "backend"',
        "drive_forge.py",
        "evaluate T01",
    ):
        assert fragment in commands


def test_check_environment_points_python_at_the_copy(tmp_path: Path) -> None:
    env, cwd = H.check_environment(BY_ID["E01"], tmp_path)
    assert env["PYTHONPATH"] == str(tmp_path / "src") and cwd == tmp_path
    env, cwd = H.check_environment(BY_ID["T01"], tmp_path)
    assert (
        env["PYTHONPATH"] == str(tmp_path / "backend") and cwd == tmp_path / "backend" and env["SECRET_KEY"]
    )


def test_list_command_prints_all_ids(capsys: pytest.CaptureFixture[str]) -> None:
    assert runner.main(["list"]) == 0
    out = capsys.readouterr().out
    assert all(c.id in out for c in CHALLENGES)


def test_unknown_id_is_rejected(capsys: pytest.CaptureFixture[str]) -> None:
    assert runner.main(["prepare", "Z99"]) == 2


def test_evaluate_without_prepare_is_rejected(tmp_path: Path) -> None:
    assert runner.main(["evaluate", "E01", "--run-dir", str(tmp_path)]) == 2


def test_evaluate_scores_a_fake_delivery_without_running_anything_heavy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Evaluate on a tiny fake repo: the check and the suite are stubbed, the file bookkeeping is real."""
    challenge = BY_ID["E03"]
    run_dir = tmp_path / "run"
    pristine = run_dir / "repo"
    (pristine / "tests").mkdir(parents=True)
    (pristine / "src" / "click").mkdir(parents=True)
    (pristine / "src" / "click" / "formatting.py").write_text("x = 1\n", encoding="utf-8")
    runner.write_json(run_dir / "manifest.json", H.snapshot(pristine))
    delivered = run_dir / "workspace" / "repo"
    H.copy_repo(pristine, delivered)
    (delivered / "tests" / "test_formatting.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(H, "run_existing_suite", lambda *a, **k: {"status": "pass"})
    monkeypatch.setattr(
        H, "run_mutation_check", lambda *a, **k: {"status": "pass", "killed": 6, "total": 6, "survivors": []}
    )
    args = argparse.Namespace(seconds=42, cost=0.12, where_lost="")
    result = runner.evaluate(challenge, run_dir, delivered, "python", args)
    assert result["passed"] is True and result["new_tests_added"] == 1 and result["seconds"] == 42
    assert result["changed_files"]["added"] == ["tests/test_formatting.py"]
    assert json.loads((run_dir / "result.json").read_text(encoding="utf-8"))["id"] == "E03"
    assert "PASS" in runner.summary_line(result)

    (delivered / "src" / "click" / "formatting.py").write_text("x = 2\n", encoding="utf-8")
    result = runner.evaluate(challenge, run_dir, delivered, "python", args)
    assert result["passed"] is False and "source files were changed" in result["fail_reasons"]


# --- tests that need the pinned clones (skipped when they are absent) -----------------------------------------


needs_clones = pytest.mark.skipif(
    not (CLONES / "click" / "src" / "click").is_dir(), reason="benchmark clones not downloaded"
)


@needs_clones
def test_seeded_edits_and_mutants_apply_to_the_clone(tmp_path: Path) -> None:
    """Every seeded patch, reference edit and mutant must match exactly once in the pinned source; the clone is only read."""
    for challenge in CHALLENGES:
        root = CLONES / challenge.repo
        if not root.is_dir():
            continue
        for edit in (*challenge.seeded, *challenge.mutants):
            scratch = tmp_path / challenge.id / Path(edit.path).name
            scratch.parent.mkdir(parents=True, exist_ok=True)
            relative = Path(edit.path).name
            scratch.write_bytes((root / edit.path).read_bytes())
            H.apply_edits(scratch.parent, (H.Edit(relative, edit.old, edit.new),))


@needs_clones
def test_expected_source_files_exist_in_the_clone() -> None:
    for challenge in CHALLENGES:
        root = CLONES / challenge.repo
        if not root.is_dir():
            continue
        for relative in challenge.expected_files:
            if relative.startswith(("tests/", "backend/tests/")) or relative.endswith("alembic/versions"):
                continue
            assert (root / relative).exists(), f"{challenge.id}: {relative}"


@needs_clones
def test_prepare_copies_applies_the_seed_and_leaves_the_clone_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(H, "run_check_file", lambda *a, **k: {"status": "fail"})
    monkeypatch.setattr(H, "run_existing_suite", lambda *a, **k: {"status": "pass"})
    challenge = BY_ID["E02"]
    before = H.snapshot(CLONES / "click")
    baseline = runner.prepare(challenge, tmp_path / "E02", sys.executable)
    assert (tmp_path / "E02" / "repo" / "src" / "click" / "utils.py").read_text(encoding="utf-8").count(
        "total_length >= max_length"
    ) == 1
    assert (tmp_path / "E02" / "prompt.txt").read_text(encoding="utf-8").startswith(challenge.brief)
    assert (tmp_path / "E02" / "manifest.json").exists() and "check" in baseline
    assert H.snapshot(CLONES / "click") == before
