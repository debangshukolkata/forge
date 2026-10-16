"""A test run that reaches 100% and then hangs gets a hint instead of being re-run unchanged (office laptop, 2026-10-16)."""

from __future__ import annotations

from forge.toolkit.shell import hung_after_last_test


def test_progress_at_100_percent_without_a_summary_is_a_hang() -> None:
    assert hung_after_last_test(
        "..... [100%]\n[timed out after 120s; the process and its children were stopped."
    )


def test_a_finished_run_or_other_output_is_not() -> None:
    assert not hung_after_last_test("..... [100%]\n5 passed in 3.21s")
    assert not hung_after_last_test("1 failed, 4 passed in 2.0s [100%]")
    assert not hung_after_last_test("server started; waiting")
