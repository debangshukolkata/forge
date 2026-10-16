"""A test run that reaches 100% and then hangs gets a hint instead of being re-run unchanged (office laptop, 2026-10-16)."""

from __future__ import annotations

from pathlib import Path

from forge.toolkit.shell import hung_after_last_test


def test_progress_at_100_percent_without_a_summary_is_a_hang() -> None:
    assert hung_after_last_test(
        "..... [100%]\n[timed out after 120s; the process and its children were stopped."
    )


def test_a_finished_run_or_other_output_is_not() -> None:
    assert not hung_after_last_test("..... [100%]\n5 passed in 3.21s")
    assert not hung_after_last_test("1 failed, 4 passed in 2.0s [100%]")
    assert not hung_after_last_test("server started; waiting")


def test_commands_the_model_runs_get_pytest_without_the_cache_plugin(
    tmp_path: Path, original_repo: Path
) -> None:
    # D-458: plain pytest hung after [100%] on the office laptop; the model's own commands now behave like DebCraft's gate commands.
    from forge.toolkit.shell import ShellSession
    from forge.workspace.create import create_workspace

    shell = ShellSession(create_workspace(original_repo, tmp_path / "ws", "backend"))
    options = shell.environment()["PYTEST_ADDOPTS"]
    assert "-p no:cacheprovider" in options
    assert options.count("cacheprovider") == 1
