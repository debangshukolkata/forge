"""Order pricing for a small shop."""

from __future__ import annotations

TAX_RATE = 0.18


def apply_discount(subtotal: float, percent: float) -> float:
    """Takes `percent` off the subtotal."""
    return subtotal * (1 - percent / 100)


def line_total(unit_price: float, quantity: int) -> float:
    return unit_price * quantity


def order_total(lines: list[tuple[float, int]], discount_percent: float = 0.0) -> float:
    """Sum of the lines, plus tax, minus the discount. Rounded to cents."""
    subtotal = sum(line_total(price, qty) for price, qty in lines)
    with_tax = subtotal * (1 + TAX_RATE)
    return round(apply_discount(with_tax, discount_percent), 2)
