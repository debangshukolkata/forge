"""Reports over the stored invoices."""

from __future__ import annotations

from datetime import date

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


def mrr(storage: Storage, on: date) -> int:
    """Monthly recurring revenue: the plan prices of the subscriptions running on `on`."""
    return sum(
        storage.plan(s.plan_id).monthly_cents
        for s in storage.subscriptions.values()
        if s.start <= on and (s.end is None or on <= s.end)
    )


def customer_statement(storage: Storage, customer_id: int) -> str:
    customer = storage.customer(customer_id)
    lines = [f"Statement for {customer.name} (#{customer.id})"]
    for invoice in storage.invoices_for(customer_id):
        lines.append(f"  #{invoice.id} {invoice.issued.isoformat()} {format_money(invoice.total_cents)}")
    mine = sorted((s for s in storage.subscriptions.values() if s.customer_id == customer_id), key=lambda s: s.id)
    if mine:
        lines.append("Subscriptions:")
        for s in mine:
            name = storage.plan(s.plan_id).name
            span = f"since {s.start.isoformat()}" if s.end is None else f"{s.start.isoformat()}..{s.end.isoformat()}"
            lines.append(f"  #{s.id} {name} {span}")
    return "\n".join(lines)
