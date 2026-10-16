"""A time box for a headless run (D-460): start at a clock time, work until a clock time, then wrap up.

`forge run --workspace W -p "..." --start-at 14:00 --until 17:00 [--wrap-up "update memory and the progress notes"]`

The deadline is soft and then hard. Ten minutes before `--until` the running turn is interrupted and the model is told to stop starting new work, bring the project to a clean state and do the wrap-up the user asked for
(default: update memory and the progress notes and say what is left). After the grace period the run is stopped. A model call can take minutes, so "17:00" means "wrapped up by about 17:00, stopped by 17:10 at the latest".
Pure logic here (parsing and the default texts); the waiting and the interrupt are in `engine/headless.py`."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

DEFAULT_WRAP_MINUTES = 10
DEFAULT_GRACE_MINUTES = 10
DEFAULT_WRAP_UP = (
    "Update memory (memory_write) with what you learned about this project, update the task list and the progress notes with what is done, what is in progress and what comes next, "
    "and say in your last message what is left."
)
CLOCK = re.compile(r"^\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*$")


class TimeBoxError(ValueError):
    """The time could not be read, or the times do not fit together."""


def parse_when(text: str, now: datetime, after: datetime | None = None) -> datetime:
    """`14:00` is the next 14:00 (today when it is still ahead, else tomorrow); `2026-10-17 14:00` or `2026-10-17T14:00` is that moment.
    With `after` (the start of the box) a clock time means the next occurrence after it, so "start 22:00, until 06:00" ends tomorrow morning."""
    reference = after or now
    match = CLOCK.match(text)
    if match:
        hour, minute, second = int(match[1]), int(match[2]), int(match[3] or 0)
        if hour > 23 or minute > 59 or second > 59:
            raise TimeBoxError(f"'{text}' is not a time of day (use 14:00 or 2026-10-17 14:00)")
        moment = reference.replace(hour=hour, minute=minute, second=second, microsecond=0)
        if moment <= reference:
            moment += timedelta(days=1)
        return moment
    try:
        return datetime.fromisoformat(text.strip().replace(" ", "T", 1))
    except ValueError as error:
        raise TimeBoxError(f"'{text}' is not a time (use 14:00 or 2026-10-17 14:00)") from error


@dataclass(frozen=True)
class TimeBox:
    start_at: datetime | None
    until: datetime | None
    wrap_minutes: int = DEFAULT_WRAP_MINUTES
    grace_minutes: int = DEFAULT_GRACE_MINUTES
    wrap_up: str = DEFAULT_WRAP_UP

    @property
    def wrap_starts(self) -> datetime | None:
        if self.until is None:
            return None
        return self.until - timedelta(minutes=self.wrap_minutes)

    @property
    def hard_stop(self) -> datetime | None:
        if self.until is None:
            return None
        return self.until + timedelta(minutes=self.grace_minutes)

    def wrap_message(self, now: datetime) -> str:
        left = max(int((self.until - now).total_seconds() // 60), 0) if self.until else 0
        return (
            f"The time box is nearly over (it is {now:%H:%M}; the run ends at {self.until:%H:%M}, about {left} minutes from now). Stop starting new work. "
            "Finish only the step you are on, bring the project to a clean state (nothing half-edited; run the tests; if some fail, say which and leave them as they are), "
            f"then wrap up: {self.wrap_up} Do not begin another task."
        )


def build_timebox(
    start_at: str | None,
    until: str | None,
    wrap_up: str | None,
    now: datetime,
    wrap_minutes: int = DEFAULT_WRAP_MINUTES,
    grace_minutes: int = DEFAULT_GRACE_MINUTES,
) -> TimeBox | None:
    """None when neither time was given. Raises TimeBoxError for an unreadable time, an end that is not after the start, or a box shorter than its own wrap-up."""
    if not start_at and not until:
        return None
    start = parse_when(start_at, now) if start_at else None
    end = parse_when(until, now, after=start) if until else None
    if start and end and end <= start:
        raise TimeBoxError(f"--until {end:%Y-%m-%d %H:%M} is not after --start-at {start:%Y-%m-%d %H:%M}")
    if end and end - (start or now) <= timedelta(minutes=wrap_minutes):
        raise TimeBoxError(
            f"the box is shorter than its {wrap_minutes}-minute wrap-up: choose a later --until"
        )
    return TimeBox(start, end, wrap_minutes, grace_minutes, (wrap_up or DEFAULT_WRAP_UP).strip())
