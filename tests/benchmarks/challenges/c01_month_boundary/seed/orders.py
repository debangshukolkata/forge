"""Order records as the sales system exports them."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Order:
    id: int
    placed_at: str  # ISO 8601, always UTC: "2026-03-31T20:30:00+00:00"
    amount_cents: int
