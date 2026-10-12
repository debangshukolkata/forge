"""Invoice totals for the three kinds of customer."""

from __future__ import annotations

TAX_RATE = 0.2


def invoice_total_retail(lines: list[tuple[float, int]]) -> float:
    subtotal = 0.0
    for unit_price, quantity in lines:
        if quantity < 0 or unit_price < 0:
            raise ValueError("negative price or quantity")
        subtotal += unit_price * quantity
    discount_rate = 0.0
    taxed = subtotal * (1 - discount_rate) * (1 + TAX_RATE)
    return round(taxed, 2)


def invoice_total_wholesale(lines: list[tuple[float, int]]) -> float:
    subtotal = 0.0
    for unit_price, quantity in lines:
        if quantity < 0 or unit_price < 0:
            raise ValueError("negative price or quantity")
        subtotal += unit_price * quantity
    discount_rate = 0.15 if subtotal >= 1000 else 0.05
    taxed = subtotal * (1 - discount_rate) * (1 + TAX_RATE)
    return round(taxed, 2)


def invoice_total_member(lines: list[tuple[float, int]]) -> float:
    subtotal = 0.0
    for unit_price, quantity in lines:
        if quantity < 0 or unit_price < 0:
            raise ValueError("negative price or quantity")
        subtotal += unit_price * quantity
    discount_rate = 0.10
    taxed = subtotal * (1 - discount_rate) * (1 + TAX_RATE)
    return round(taxed, 2)
