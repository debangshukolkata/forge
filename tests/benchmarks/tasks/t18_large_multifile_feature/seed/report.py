"""Reports over the stored invoices."""

from __future__ import annotations

from storage import Storage


def format_money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def revenue_by_month(storage: Storage) -> dict[str, int]:
    """Invoice totals per month of issue, keyed 'YYYY-MM', in month order."""
    totals: dict[str, int] = {}
    for invoice in storage.invoices.values():
        key = invoice.issued.strftime("%Y-%m")
        totals[key] = totals.get(key, 0) + invoice.total_cents
    return dict(sorted(totals.items()))


def customer_statement(storage: Storage, customer_id: int) -> str:
    customer = storage.customer(customer_id)
    lines = [f"Statement for {customer.name} (#{customer.id})"]
    for invoice in storage.invoices_for(customer_id):
        lines.append(f"  #{invoice.id} {invoice.issued.isoformat()} {format_money(invoice.total_cents)}")
    return "\n".join(lines)
