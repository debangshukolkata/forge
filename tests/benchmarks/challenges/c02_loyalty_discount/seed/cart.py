"""A shopping cart. Prices are integers in cents."""

from __future__ import annotations

from dataclasses import dataclass, field

SHIPPING_CENTS = 499
FREE_SHIPPING_FROM_CENTS = 5_000


@dataclass
class Item:
    sku: str
    unit_cents: int
    quantity: int = 1


@dataclass
class Customer:
    id: int
    name: str
    orders_placed: int = 0
    member_since_year: int | None = None


@dataclass
class Cart:
    customer: Customer
    items: list[Item] = field(default_factory=list)
    coupon_percent: int = 0  # a marketing coupon, 0 to 100

    def add(self, sku: str, unit_cents: int, quantity: int = 1) -> None:
        self.items.append(Item(sku, unit_cents, quantity))

    def subtotal_cents(self) -> int:
        return sum(item.unit_cents * item.quantity for item in self.items)

    def shipping_cents(self) -> int:
        return 0 if self.subtotal_cents() >= FREE_SHIPPING_FROM_CENTS else SHIPPING_CENTS

    def total_cents(self) -> int:
        discounted = self.subtotal_cents() * (100 - self.coupon_percent) // 100
        return discounted + self.shipping_cents()
