"""The time box of a headless run (D-460): parsing the times, the wrap-up and the hard stop."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from forge.engine import headless
from forge.engine.headless import EXIT_TIMEBOX, run_headless
from forge.engine.timebox import TimeBox, TimeBoxError, build_timebox, parse_when
from forge.protocol.inputs import Interrupt, SendMessage

NOW = datetime(2026, 10, 16, 13, 0, 0)


def test_a_clock_time_means_the_next_one_and_an_end_is_counted_from_the_start() -> None:
    assert parse_when("14:00", NOW) == datetime(2026, 10, 16, 14, 0)
    assert parse_when("12:00", NOW) == datetime(2026, 10, 17, 12, 0)  # already past today: tomorrow
    assert parse_when("2026-10-17 09:30", NOW) == datetime(2026, 10, 17, 9, 30)
    start = datetime(2026, 10, 16, 22, 0)
    assert parse_when("06:00", NOW, after=start) == datetime(2026, 10, 17, 6, 0)  # overnight
    with pytest.raises(TimeBoxError):
        parse_when("25:00", NOW)
    with pytest.raises(TimeBoxError):
        parse_when("later", NOW)


def test_the_box_has_a_wrap_up_start_a_hard_stop_and_refuses_nonsense() -> None:
    box = build_timebox("14:00", "17:00", None, NOW)
    assert box is not None
    assert box.wrap_starts == datetime(2026, 10, 16, 16, 50) and box.hard_stop == datetime(
        2026, 10, 16, 17, 10
    )
    assert "memory" in box.wrap_message(datetime(2026, 10, 16, 16, 50)) and "17:00" in box.wrap_message(NOW)
    custom = build_timebox(None, "17:00", "Write the hand-over note.", NOW)
    assert custom is not None and "Write the hand-over note." in custom.wrap_message(NOW)
    assert build_timebox(None, None, None, NOW) is None
    with pytest.raises(TimeBoxError):
        build_timebox("14:00", "2026-10-16 13:00", None, NOW)  # ends before it starts
    with pytest.raises(TimeBoxError):
        build_timebox(None, "13:05", None, NOW)  # shorter than its own wrap-up


class FakeHost:
    """Just what run_headless uses. The first message starts a turn that only ends when it is interrupted; the wrap-up message starts one that ends by itself (or never, for the hard stop)."""

    def __init__(self, wrap_turn_ends: bool) -> None:
        self.wrap_turn_ends = wrap_turn_ends
        self.messages: list[str] = []
        self.interrupts = 0
        self.busy = False
        self.published: list[str] = []
        self._turn: asyncio.Task[None] | None = None
        host = self
        self.bus = SimpleNamespace(
            last_seq=0, subscribe=lambda since_seq=0: _Subscription(), publish=host._publish
        )
        state = SimpleNamespace(exported=False, tasks=[], resume_summary=lambda: "resumable")
        self.orchestrator = SimpleNamespace(state=state, set_cadence=lambda _c: None, wait_idle=_nothing)

    @property
    def inputs_empty(self) -> bool:
        return True

    async def _publish(self, _kind: Any, payload: dict[str, Any]) -> None:
        self.published.append(str(payload.get("text")))

    async def submit(self, user_input: Any) -> None:
        if isinstance(user_input, Interrupt):
            self.interrupts += 1
            if self._turn is not None:
                self._turn.cancel()
            return
        assert isinstance(user_input, SendMessage)
        self.messages.append(user_input.text)
        self._turn = asyncio.create_task(self._run_turn(len(self.messages) == 1))

    async def _run_turn(self, first: bool) -> None:
        self.busy = True
        try:
            await asyncio.sleep(3600 if first or not self.wrap_turn_ends else 0.15)
        finally:
            self.busy = False

    async def run(self) -> None:
        await asyncio.sleep(3600)

    async def close(self) -> None:
        return None


class _Subscription:
    def __aiter__(self) -> _Subscription:
        return self

    async def __anext__(self) -> Any:
        await asyncio.sleep(3600)

    def close(self) -> None:
        return None


async def _nothing() -> None:
    return None


def fast_clock(base: datetime, virtual_seconds_per_second: float) -> Any:
    started = time.monotonic()
    return lambda: base + timedelta(seconds=(time.monotonic() - started) * virtual_seconds_per_second)


async def test_at_the_soft_deadline_the_turn_is_interrupted_and_the_wrap_up_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(headless, "POLL_SECONDS", 0.02)
    clock = fast_clock(NOW, 200)  # 2 virtual minutes pass in 0.6 s
    box = TimeBox(None, NOW + timedelta(minutes=12), 10, 10, "Update memory.")
    host = FakeHost(wrap_turn_ends=True)
    result = await asyncio.wait_for(run_headless(host, "build it", False, box, clock), 20)  # type: ignore[arg-type]
    assert host.interrupts == 1 and len(host.messages) == 2
    assert "time box is nearly over" in host.messages[1] and "Update memory." in host.messages[1]
    assert result.exit_code == EXIT_TIMEBOX and "wrapped up" in result.activity
    assert any("wrapping up" in text for text in host.published)


async def test_a_wrap_up_that_never_ends_is_stopped_at_the_hard_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(headless, "POLL_SECONDS", 0.02)
    clock = fast_clock(NOW, 200)
    box = TimeBox(None, NOW + timedelta(minutes=12), 10, 10, "Update memory.")
    host = FakeHost(wrap_turn_ends=False)
    result = await asyncio.wait_for(run_headless(host, "build it", False, box, clock), 30)  # type: ignore[arg-type]
    assert host.interrupts == 2  # one for the wrap-up, one at the hard limit
    assert result.exit_code == EXIT_TIMEBOX and "hard limit" in result.activity
