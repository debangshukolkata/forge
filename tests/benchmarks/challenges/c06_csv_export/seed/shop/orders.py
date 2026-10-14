"""Orders."""

from __future__ import annotations

from dataclasses import dataclass

from shop.money import format_money
from shop.result import Result


@dataclass(frozen=True)
class Order:
    id: int
    customer: str
    total_cents: int
    status: str  # "open", "paid" or "cancelled"


VALID_STATUSES = ("open", "paid", "cancelled")


def describe(order: Order) -> str:
    return f"#{order.id} {order.customer}: {format_money(order.total_cents)} ({order.status})"


def mark_paid(order: Order) -> Result[Order]:
    if order.status == "cancelled":
        return Result.failure(f"order {order.id} is cancelled and cannot be paid")
    return Result.success(Order(order.id, order.customer, order.total_cents, "paid"))
