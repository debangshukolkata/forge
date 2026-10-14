"""The challenge runner reads an event log into a timeline and automatic signals (no model, no run)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "benchmark"))
from run_challenges import file_checks, is_test_path, timeline


def event(kind: str, seconds: int, **payload: object) -> dict[str, object]:
    return {"type": kind, "ts": f"2026-10-15T10:00:{seconds:02d}.000+00:00", "payload": payload}


def started(seconds: int, name: str, summary: str, **arguments: object) -> dict[str, object]:
    return event(
        "tool_call_started", seconds, id=str(seconds), name=name, summary=summary, arguments=arguments
    )


def test_the_signals_say_what_came_before_the_first_edit() -> None:
    events = [
        event("user_message", 0, text="Fix it"),
        started(1, "read_file", "read report.py", path="report.py"),
        started(2, "read_file", "read timeutil.py", path="timeutil.py"),
        started(3, "run_command", "python -m pytest -q"),
        event("message_done", 4, text="I will assume finance means calendar months in IST."),
        started(
            5,
            "write_file",
            "write tests/test_boundary.py",
            path="tests/test_boundary.py",
            content="def test_x(): ...",
        ),
        started(
            6, "edit_file", "edit timeutil.py", path="timeutil.py", new_text="from zoneinfo import ZoneInfo"
        ),
    ]
    text, signals = timeline(events)
    assert "#01 read_file" in text and "MODEL  I will assume" in text
    assert signals["reads_before_first_edit"] == 2 and signals["tests_run_before_first_edit"] is True
    assert signals["test_written_before_source_edit"] is True and signals["assumptions_mentioned"] is True
    assert str(signals["first_edit"]).startswith("#4 write_file")
    assert file_checks("c01_month_boundary", Path("."), events) == {"fix_in_timeutil": True}


def test_an_edit_first_run_is_visible_and_test_paths_are_recognised() -> None:
    events = [
        started(
            1,
            "write_file",
            "write settings.py",
            path="settings.py",
            content="from pydantic import validator\n@validator('port')",
        )
    ]
    _, signals = timeline(events)
    assert (
        signals["reads_before_first_edit"] == 0
        and signals["library_checked"] is False
        and signals["test_written_before_source_edit"] is False
    )
    assert file_checks("c07_settings_model", Path("."), events) == {"v1_api_used": True, "v2_api_used": False}
    assert (
        is_test_path("tests/test_x.py")
        and is_test_path("shop/tests/conftest.py")
        and not is_test_path("shop/orders.py")
    )
