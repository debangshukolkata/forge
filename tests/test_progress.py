"""Live progress for anything that runs a while (D-219): figures from output, quiet-time notes, and the way a
running command and `monitor` report them. Real PowerShell for the command; no model involved."""

from __future__ import annotations

import asyncio
from collections import deque
from pathlib import Path
from typing import Any

import pytest

from forge.toolkit.background import BackgroundManager, BackgroundProcess, Monitor
from forge.toolkit.base import ToolContext
from forge.toolkit.powershell import run_powershell
from forge.toolkit.progress import ProgressTracker, extract_progress
from tests.test_parity import workspace  # noqa: F401  (fixture)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("tests/test_x.py::test_a PASSED                                   [ 40%]", 40.0),
        ("Downloading wheel 12.5% done", 12.5),
        ("[12/30] compiling app.py", 40.0),
        ("Processing 3 of 9 files", 33.3),
        ("(5/5)", 100.0),
        ("Fetched 250% of nothing", None),  # not a plausible figure
        ("version 3.13.5 released", None),
        ("copied 12/9 files", None),  # more done than total: not a progress figure
        ("just a plain line", None),
    ],
)
def test_progress_figures_are_found_in_common_shapes(line: str, expected: float | None) -> None:
    assert extract_progress(line) == expected


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


async def test_the_tracker_reports_changes_at_most_every_two_seconds() -> None:
    reports: list[dict[str, Any]] = []

    async def report(progress: dict[str, Any]) -> None:
        reports.append(progress)

    clock = Clock()
    tracker = ProgressTracker(report, clock=clock, extra={"source": "command"})
    tracker.feed("collecting ...\nrunning 1/4\n")
    await tracker.tick()
    assert (
        reports[-1]["line"] == "running 1/4"
        and reports[-1]["percent"] == 25.0
        and reports[-1]["source"] == "command"
    )
    tracker.feed("running 2/4\n")
    clock.now += 0.5
    await tracker.tick()
    assert len(reports) == 1  # too soon
    clock.now += 2
    await tracker.tick()
    assert len(reports) == 2 and reports[-1]["percent"] == 50.0
    clock.now += 5
    await tracker.tick()
    assert len(reports) == 2  # nothing new to say
    tracker.feed("still working, no figure on this line\n")
    clock.now += 2
    await tracker.tick()
    assert reports[-1]["percent"] == 50.0 and reports[-1]["lines"] == 4  # the last figure is kept


async def test_a_redrawn_progress_bar_counts_as_the_current_line() -> None:
    reports: list[dict[str, Any]] = []

    async def report(progress: dict[str, Any]) -> None:
        reports.append(progress)

    tracker = ProgressTracker(report, clock=Clock())
    tracker.feed("\x1b[32mDownloading 10%\x1b[0m\rDownloading 55%\rDownloading 90%")  # no newline at all
    await tracker.tick()
    assert reports[-1]["line"] == "Downloading 90%" and reports[-1]["percent"] == 90.0


async def test_a_quiet_program_is_noticed_and_the_note_repeats_each_minute() -> None:
    reports: list[dict[str, Any]] = []

    async def report(progress: dict[str, Any]) -> None:
        reports.append(progress)

    clock = Clock()
    tracker = ProgressTracker(report, clock=clock)
    tracker.feed("building\n")
    await tracker.tick()
    clock.now += 100
    await tracker.tick()
    assert reports[-1]["stalled_s"] is None  # not quiet long enough yet
    clock.now += 30
    await tracker.tick()
    assert reports[-1]["stalled_s"] == 130
    clock.now += 20
    await tracker.tick()
    assert len([r for r in reports if r["stalled_s"]]) == 1  # not again at once
    clock.now += 50
    await tracker.tick()
    assert len([r for r in reports if r["stalled_s"]]) == 2
    tracker.feed("building again\n")  # output resumes: the quiet note goes away
    clock.now += 2
    await tracker.tick()
    assert reports[-1]["stalled_s"] is None


async def test_a_running_powershell_command_reports_its_lines(tmp_path: Path) -> None:
    reports: list[dict[str, Any]] = []

    async def report(progress: dict[str, Any]) -> None:
        reports.append(progress)

    command = '1..4 | ForEach-Object { Write-Output "step $_/4"; Start-Sleep -Milliseconds 900 }'
    outcome = await run_powershell(
        command, tmp_path, dict(__import__("os").environ), 60, tmp_path, on_progress=report
    )
    assert outcome.exit_code == 0 and "step 4/4" in outcome.output
    assert reports, "a command that runs for several seconds reports while it runs"
    assert all(r["line"].startswith("step ") for r in reports)
    percents = [r["percent"] for r in reports]
    assert percents == sorted(percents) and 0 < percents[-1] <= 100


class FakeProcess:
    def __init__(self) -> None:
        self.returncode: int | None = None
        self.pid = 0


async def test_monitor_shows_progress_while_it_waits_and_flags_trouble(workspace: Any) -> None:  # noqa: F811
    emitted: list[tuple[str, dict[str, Any]]] = []

    async def publish(kind: str, payload: dict[str, Any]) -> None:
        emitted.append((kind, payload))

    process = FakeProcess()
    entry = BackgroundProcess(name="suite", command="pytest", process=process, port=None, lines=deque())  # type: ignore[arg-type]
    manager = BackgroundManager()
    manager.processes["suite"] = entry
    context = ToolContext(workspace=workspace, background=manager, publish=publish)

    async def output() -> None:
        for text in (
            "collected 10 items",
            "tests/a.py ..  [ 20%]",
            "tests/b.py F  [ 60%]",
            "Traceback (most recent call last):",
        ):
            await asyncio.sleep(0.5)
            entry.lines.append(text)
            entry.total_lines += 1
        await asyncio.sleep(0.5)
        process.returncode = 1

    writer = asyncio.create_task(output())
    result = await Monitor().run(Monitor.Args(name="suite", timeout_s=20), context)
    await writer
    assert "exited (1)" in result.content and "shows trouble" in result.content
    progress = [payload for kind, payload in emitted if kind == "tool_progress"]
    assert progress and all(p["source"] == "monitor" and p["name"] == "suite" for p in progress)
    assert any(p["percent"] == 60.0 for p in progress)
