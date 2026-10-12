"""Invoice totals for the three kinds of customer."""

from __future__ import annotations

from collections.abc import Callable

TAX_RATE = 0.2


def _wholesale_rate(subtotal: float) -> float:
    return 0.15 if subtotal >= 1000 else 0.05


DISCOUNT_RATES: dict[str, Callable[[float], float]] = {
    "retail": lambda subtotal: 0.0,
    "wholesale": _wholesale_rate,
    "member": lambda subtotal: 0.10,
}


def calculate_total(lines: list[tuple[float, int]], customer_type: str) -> float:
    if customer_type not in DISCOUNT_RATES:
        raise ValueError(f"unknown customer type: {customer_type}")
    subtotal = 0.0
    for unit_price, quantity in lines:
        if quantity < 0 or unit_price < 0:
            raise ValueError("negative price or quantity")
        subtotal += unit_price * quantity
    discount_rate = DISCOUNT_RATES[customer_type](subtotal)
    return round(subtotal * (1 - discount_rate) * (1 + TAX_RATE), 2)


def invoice_total_retail(lines: list[tuple[float, int]]) -> float:
    return calculate_total(lines, "retail")


def invoice_total_wholesale(lines: list[tuple[float, int]]) -> float:
    return calculate_total(lines, "wholesale")


def invoice_total_member(lines: list[tuple[float, int]]) -> float:
    return calculate_total(lines, "member")
