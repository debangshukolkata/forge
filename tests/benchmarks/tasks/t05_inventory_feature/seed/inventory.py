"""A small stock-keeping module."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Item:
    sku: str
    name: str
    quantity: int


class Inventory:
    def __init__(self) -> None:
        self._items: dict[str, Item] = {}

    def add(self, sku: str, name: str, quantity: int = 0) -> Item:
        """Create an item, or add to the quantity of an existing sku (the name is kept)."""
        if quantity < 0:
            raise ValueError("quantity cannot be negative")
        if sku in self._items:
            self._items[sku].quantity += quantity
        else:
            self._items[sku] = Item(sku, name, quantity)
        return self._items[sku]

    def remove(self, sku: str, quantity: int) -> Item:
        """Take stock out. Raises KeyError for an unknown sku and ValueError if there is not enough."""
        item = self._items[sku]
        if quantity > item.quantity:
            raise ValueError(f"only {item.quantity} of {sku} in stock")
        item.quantity -= quantity
        return item

    def quantity(self, sku: str) -> int:
        return self._items[sku].quantity if sku in self._items else 0

    def items(self) -> list[Item]:
        return sorted(self._items.values(), key=lambda item: item.sku)
