"""Late fees."""

from __future__ import annotations

from datetime import date

FINE_CENTS_PER_DAY = 25


def fine_for(due: date, returned: date) -> int:
    """Cents owed for a book handed back on `returned` that was due on `due`."""
    late_days = (returned - due).days
    return max(late_days, 0) * FINE_CENTS_PER_DAY
