"""Monthly sales report."""

from __future__ import annotations

from collections.abc import Iterable

from orders import Order
from timeutil import to_report_date


def monthly_total_cents(orders: Iterable[Order], year: int, month: int) -> int:
    """Sum of the orders that belong to the given month in the reporting timezone."""
    total = 0
    for order in orders:
        day = to_report_date(order.placed_at)
        if day.year == year and day.month == month:
            total += order.amount_cents
    return total


def monthly_counts(orders: Iterable[Order]) -> dict[tuple[int, int], int]:
    counts: dict[tuple[int, int], int] = {}
    for order in orders:
        day = to_report_date(order.placed_at)
        key = (day.year, day.month)
        counts[key] = counts.get(key, 0) + 1
    return counts
