"""Date helpers shared by the reports."""

from __future__ import annotations

from datetime import date, datetime

REPORT_TIMEZONE = "Asia/Kolkata"


def parse_timestamp(text: str) -> datetime:
    """An ISO 8601 string as a datetime (keeps the offset it came with)."""
    return datetime.fromisoformat(text)


def to_report_date(text: str, timezone: str = REPORT_TIMEZONE) -> date:
    """The calendar date an order belongs to in the reporting timezone."""
    stamp = parse_timestamp(text)
    return stamp.date()
