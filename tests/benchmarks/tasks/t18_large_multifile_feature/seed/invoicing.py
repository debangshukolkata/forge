"""One-off invoices."""

from __future__ import annotations

from datetime import date

from models import Invoice, InvoiceLine
from storage import Storage


def create_invoice(storage: Storage, customer_id: int, items: list[tuple[str, int]], issued: date) -> Invoice:
    """An invoice for fixed items [(description, cents)]; unknown customer raises KeyError."""
    storage.customer(customer_id)
    if not items:
        raise ValueError("an invoice needs at least one line")
    lines = [InvoiceLine(description, cents) for description, cents in items]
    return storage.add_invoice(Invoice(0, customer_id, issued, lines))
