"""Keeps customers, plans and invoices, optionally in one JSON file.

File format (kept stable, other tools read it):
    {"next_id": {"customer": 1, "plan": 1, "invoice": 1},
     "customers": [{"id": 1, "name": "Ana"}],
     "plans": [{"id": 1, "name": "Pro", "monthly_cents": 3000}],
     "invoices": [{"id": 1, "customer_id": 1, "issued": "2026-01-31",
                   "period_start": null, "period_end": null,
                   "lines": [{"description": "Setup", "amount_cents": 500}]}]}
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from models import Customer, Invoice, InvoiceLine, Plan, Subscription


def _day(text: str | None) -> date | None:
    return date.fromisoformat(text) if text else None


def _iso(day: date | None) -> str | None:
    return day.isoformat() if day else None


class Storage:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.customers: dict[int, Customer] = {}
        self.plans: dict[int, Plan] = {}
        self.invoices: dict[int, Invoice] = {}
        self.subscriptions: dict[int, Subscription] = {}
        self.next_id = {"customer": 1, "plan": 1, "invoice": 1}
        if path is not None and path.exists():
            self._load(json.loads(path.read_text(encoding="utf-8")))

    # -- lookups: unknown ids raise KeyError --
    def customer(self, customer_id: int) -> Customer:
        return self.customers[customer_id]

    def plan(self, plan_id: int) -> Plan:
        return self.plans[plan_id]

    def subscription(self, subscription_id: int) -> Subscription:
        return self.subscriptions[subscription_id]

    # -- adding --
    def _take_id(self, kind: str) -> int:
        number = self.next_id[kind]
        self.next_id[kind] = number + 1
        return number

    def add_customer(self, name: str) -> Customer:
        if not name.strip():
            raise ValueError("a customer needs a name")
        customer = Customer(self._take_id("customer"), name.strip())
        self.customers[customer.id] = customer
        return customer

    def add_plan(self, name: str, monthly_cents: int) -> Plan:
        if not name.strip() or monthly_cents < 0:
            raise ValueError("a plan needs a name and a price of 0 or more")
        plan = Plan(self._take_id("plan"), name.strip(), monthly_cents)
        self.plans[plan.id] = plan
        return plan

    def add_invoice(self, invoice: Invoice) -> Invoice:
        invoice.id = self._take_id("invoice")
        self.invoices[invoice.id] = invoice
        return invoice

    def add_subscription(self, customer_id: int, plan_id: int, start: date) -> Subscription:
        self.customer(customer_id)
        self.plan(plan_id)
        number = max(self.subscriptions, default=0) + 1  # derived, so "next_id" in the file stays as it was
        subscription = Subscription(number, customer_id, plan_id, start)
        self.subscriptions[number] = subscription
        return subscription

    def invoices_for(self, customer_id: int) -> list[Invoice]:
        return [i for i in sorted(self.invoices.values(), key=lambda i: i.id) if i.customer_id == customer_id]

    # -- persistence --
    def save(self) -> None:
        if self.path is None:
            return
        data = {
            "next_id": dict(self.next_id),
            "customers": [{"id": c.id, "name": c.name} for c in self.customers.values()],
            "plans": [{"id": p.id, "name": p.name, "monthly_cents": p.monthly_cents} for p in self.plans.values()],
            "invoices": [
                {
                    "id": i.id,
                    "customer_id": i.customer_id,
                    "issued": i.issued.isoformat(),
                    "period_start": _iso(i.period_start),
                    "period_end": _iso(i.period_end),
                    "lines": [{"description": l.description, "amount_cents": l.amount_cents} for l in i.lines],
                }
                for i in self.invoices.values()
            ],
            "subscriptions": [
                {"id": x.id, "customer_id": x.customer_id, "plan_id": x.plan_id, "start": _iso(x.start), "end": _iso(x.end)}
                for x in self.subscriptions.values()
            ],
        }
        self.path.write_text(json.dumps(data, indent=1), encoding="utf-8")

    def _load(self, data: dict) -> None:  # type: ignore[type-arg]
        self.next_id.update(data.get("next_id", {}))
        for row in data.get("customers", []):
            self.customers[row["id"]] = Customer(row["id"], row["name"])
        for row in data.get("plans", []):
            self.plans[row["id"]] = Plan(row["id"], row["name"], row["monthly_cents"])
        for row in data.get("subscriptions", []):
            self.subscriptions[row["id"]] = Subscription(
                row["id"], row["customer_id"], row["plan_id"], date.fromisoformat(row["start"]), _day(row.get("end"))
            )
        for row in data.get("invoices", []):
            lines = [InvoiceLine(l["description"], l["amount_cents"]) for l in row["lines"]]
            self.invoices[row["id"]] = Invoice(
                row["id"], row["customer_id"], date.fromisoformat(row["issued"]), lines,
                _day(row.get("period_start")), _day(row.get("period_end")),
            )  # fmt: skip
