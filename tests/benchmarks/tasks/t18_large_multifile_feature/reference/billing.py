"""Recurring subscriptions: subscribe, cancel and bill a month with proration."""

from __future__ import annotations

import calendar
from datetime import date

from models import Invoice, InvoiceLine, Subscription
from storage import Storage


def subscribe(storage: Storage, customer_id: int, plan_id: int, start: date) -> Subscription:
    storage.customer(customer_id)
    storage.plan(plan_id)
    for other in storage.subscriptions.values():
        if (
            other.customer_id == customer_id
            and other.plan_id == plan_id
            and (other.end is None or other.end >= start)
        ):
            raise ValueError(f"customer {customer_id} already has plan {plan_id} from {other.start.isoformat()}")
    return storage.add_subscription(customer_id, plan_id, start)


def cancel(storage: Storage, subscription_id: int, end: date) -> Subscription:
    subscription = storage.subscription(subscription_id)
    if subscription.end is not None:
        raise ValueError(f"subscription {subscription_id} is already cancelled")
    if end < subscription.start:
        raise ValueError("the last day of service cannot be before the start")
    subscription.end = end
    return subscription


def prorate(monthly_cents: int, days: int, days_in_month: int) -> int:
    """Whole cents, halves rounded up (integer arithmetic: no float or banker's rounding)."""
    return (monthly_cents * days * 2 + days_in_month) // (2 * days_in_month)


def bill_month(storage: Storage, year: int, month: int, issued: date) -> list[Invoice]:
    if not 1 <= month <= 12:
        raise ValueError(f"month must be 1 to 12, got {month}")
    days_in_month = calendar.monthrange(year, month)[1]
    first, last = date(year, month, 1), date(year, month, days_in_month)
    already = {i.customer_id for i in storage.invoices.values() if i.period_start == first}
    created: list[Invoice] = []
    for customer_id in sorted(storage.customers):
        if customer_id in already:
            continue
        lines: list[InvoiceLine] = []
        for subscription in sorted(storage.subscriptions.values(), key=lambda s: s.id):
            if subscription.customer_id != customer_id:
                continue
            active_from = max(subscription.start, first)
            active_to = min(subscription.end or last, last)
            days = (active_to - active_from).days + 1
            if days <= 0:
                continue
            plan = storage.plan(subscription.plan_id)
            label = f"{plan.name} {first:%Y-%m}"
            if days == days_in_month:
                lines.append(InvoiceLine(label, plan.monthly_cents))
            else:
                lines.append(
                    InvoiceLine(
                        f"{label} (prorated {days}/{days_in_month} days)",
                        prorate(plan.monthly_cents, days, days_in_month),
                    )
                )
        if lines:
            created.append(storage.add_invoice(Invoice(0, customer_id, issued, lines, first, last)))
    return created
