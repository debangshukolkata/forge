"""Live progress for anything that runs a while (D-219): a build, tests, an install, a download, a server.

It works from the output alone, so it needs nothing from the program or the model: the newest line, a progress
figure when the output shows one (`40%`, `[12/30]`, `3 of 9`), and a note when the program has gone quiet. The
caller turns what it reports into `tool_progress` events, which the web UI shows on the activity line."""

from __future__ import annotations

import asyncio
import contextlib
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

PERCENT = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d+)?)\s?%")
FRACTION = re.compile(r"(?<![\w.])[\[(]?(\d+)\s?(?:/|of)\s?(\d+)[\])]?(?![\w.])")
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
REPORT_EVERY_S = 2.0
STALL_AFTER_S = 120.0
STALL_REPEAT_S = 60.0

Report = Callable[[dict[str, Any]], Awaitable[None]]


def extract_progress(line: str) -> float | None:
    """0-100 when the line carries a figure: `NN%` first, else `n/m` or `n of m` with n <= m."""
    percent = PERCENT.search(line)
    if percent and float(percent.group(1)) <= 100:
        return float(percent.group(1))
    fraction = FRACTION.search(line)
    if fraction:
        done, total = int(fraction.group(1)), int(fraction.group(2))
        if 0 < total < 10_000_000 and done <= total:
            return round(100.0 * done / total, 1)
    return None


class ProgressTracker:
    """Fed the output as it arrives; reports at most every REPORT_EVERY_S, and only when something changed."""

    def __init__(
        self,
        report: Report,
        clock: Callable[[], float] = time.monotonic,
        report_every_s: float = REPORT_EVERY_S,
        stall_after_s: float = STALL_AFTER_S,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._report = report
        self._clock = clock
        self._every = report_every_s
        self._stall_after = stall_after_s
        self._extra = extra or {}
        self._started = clock()
        self._last_output = self._started
        self._last_report = float("-inf")
        self._last_stall_report = 0.0
        self._partial = ""
        self.line = ""
        self.percent: float | None = None
        self.lines = 0
        self._dirty = False

    def feed(self, text: str) -> None:
        """Output text in any chunking; a carriage return (a progress bar redrawing) starts a new line."""
        if not text:
            return
        self._last_output = self._clock()
        self._last_stall_report = 0.0
        pieces = re.split(r"\r\n|\n|\r", self._partial + ANSI.sub("", text))
        self._partial = pieces.pop()  # the unfinished end waits for its newline
        for piece in pieces:
            self._take(piece)
        if self._partial.strip():  # a bar redrawn with carriage returns never ends its line: show it as it is
            self._take(self._partial, partial=True)

    def _take(self, piece: str, partial: bool = False) -> None:
        stripped = piece.strip()
        if not stripped:
            return
        if not partial:
            self.lines += 1
        self.line = stripped[:200]
        found = extract_progress(stripped)
        if found is not None:
            self.percent = found
        self._dirty = True

    def stalled_s(self) -> int | None:
        quiet = self._clock() - self._last_output
        return int(quiet) if quiet >= self._stall_after else None

    async def tick(self) -> None:
        now = self._clock()
        stalled = self.stalled_s()
        stall_due = stalled is not None and now - self._last_stall_report >= STALL_REPEAT_S
        if not (self._dirty or stall_due) or now - self._last_report < self._every:
            return
        self._last_report = now
        self._dirty = False
        if stall_due:
            self._last_stall_report = now
        await self._report(
            {
                "line": self.line,
                "percent": self.percent,
                "lines": self.lines,
                "elapsed_s": int(now - self._started),
                "stalled_s": stalled,
                **self._extra,
            }
        )

    async def run(self) -> None:
        """Checks about once a second until cancelled (so a quiet program is still noticed)."""
        while True:
            await asyncio.sleep(1.0)
            with contextlib.suppress(Exception):  # reporting must never break the command it watches
                await self.tick()
