"""Next fire time of a 5-field cron expression."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timedelta

MONTHS = {name: number for number, name in enumerate(calendar.month_abbr) if name}
MONTHS = {name.lower(): number for name, number in MONTHS.items()}
WEEKDAYS = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
GIVE_UP_YEARS = 8


@dataclass(frozen=True)
class Field:
    values: frozenset[int]
    star: bool  # the text started with `*`


def _number(text: str, names: dict[str, int], low: int, high: int) -> int:
    if text.isdigit():
        value = int(text)
    elif text.lower() in names:
        value = names[text.lower()]
    else:
        raise ValueError(f"bad value {text!r}")
    if not low <= value <= high:
        raise ValueError(f"{value} is out of range {low}-{high}")
    return value


def _parse_field(text: str, low: int, high: int, names: dict[str, int]) -> Field:
    values: set[int] = set()
    for item in text.split(","):
        if not item:
            raise ValueError("empty list item")
        base, slash, step_text = item.partition("/")
        step = 1
        if slash:
            if not step_text.isdigit() or int(step_text) < 1:
                raise ValueError(f"bad step {step_text!r}")
            step = int(step_text)
        if base == "*":
            start, end = low, high
        elif "-" in base:
            first, _, last = base.partition("-")
            start, end = _number(first, names, low, high), _number(last, names, low, high)
            if start > end:
                raise ValueError(f"reversed range {base!r}")
        else:
            start = _number(base, names, low, high)
            end = high if slash else start
        values.update(range(start, end + 1, step))
    return Field(frozenset(values), text.startswith("*"))


def parse(expression: str) -> tuple[Field, Field, Field, Field, Field]:
    parts = expression.split()
    if len(parts) != 5:
        raise ValueError("a cron expression has 5 fields")
    minute = _parse_field(parts[0], 0, 59, {})
    hour = _parse_field(parts[1], 0, 23, {})
    day = _parse_field(parts[2], 1, 31, {})
    month = _parse_field(parts[3], 1, 12, MONTHS)
    weekday = _parse_field(parts[4], 0, 7, WEEKDAYS)
    weekday = Field(frozenset(0 if v == 7 else v for v in weekday.values), weekday.star)
    return minute, hour, day, month, weekday


def _day_matches(moment: datetime, day: Field, weekday: Field) -> bool:
    day_ok = moment.day in day.values
    weekday_ok = (moment.isoweekday() % 7) in weekday.values
    if day.star or weekday.star:
        return day_ok and weekday_ok
    return day_ok or weekday_ok


def next_run(expression: str, after: datetime) -> datetime:
    minute, hour, day, month, weekday = parse(expression)
    moment = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    limit = after.replace(year=after.year + GIVE_UP_YEARS) if not (after.month == 2 and after.day == 29) else after + timedelta(days=366 * GIVE_UP_YEARS)
    while moment <= limit:
        if moment.month not in month.values:
            moment = (moment.replace(day=1, hour=0, minute=0) + timedelta(days=32)).replace(day=1)
            continue
        if not _day_matches(moment, day, weekday):
            moment = moment.replace(hour=0, minute=0) + timedelta(days=1)
            continue
        if moment.hour not in hour.values:
            moment = moment.replace(minute=0) + timedelta(hours=1)
            continue
        if moment.minute not in minute.values:
            moment += timedelta(minutes=1)
            continue
        return moment
    raise ValueError("the expression never fires")
