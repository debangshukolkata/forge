"""Records of the small billing program. Money is always whole cents (int)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Customer:
    id: int
    name: str


@dataclass
class Plan:
    id: int
    name: str
    monthly_cents: int


@dataclass
class InvoiceLine:
    description: str
    amount_cents: int


@dataclass
class Invoice:
    id: int
    customer_id: int
    issued: date
    lines: list[InvoiceLine] = field(default_factory=list)
    period_start: date | None = None
    period_end: date | None = None

    @property
    def total_cents(self) -> int:
        return sum(line.amount_cents for line in self.lines)
