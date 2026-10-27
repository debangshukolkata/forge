"""Command line: `main(["add-customer", "Ana"], store_path)`. Prints through `out`; returns the exit code."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import TextIO

from billing import bill_month, cancel, subscribe
from invoicing import create_invoice
from report import customer_statement, format_money, mrr, revenue_by_month
from storage import Storage

USAGE = (
    "usage: add-customer NAME | add-plan NAME CENTS | invoice CUSTOMER DATE DESCRIPTION=CENTS... | report | statement CUSTOMER"
    " | subscribe CUSTOMER PLAN START | cancel SUBSCRIPTION END | bill YYYY-MM ISSUED | mrr DATE"
)


def main(argv: list[str], store_path: Path, out: TextIO = sys.stdout) -> int:
    if not argv:
        print(USAGE, file=out)
        return 2
    command, args = argv[0], argv[1:]
    storage = Storage(store_path)
    try:
        if command == "add-customer" and len(args) == 1:
            customer = storage.add_customer(args[0])
            print(f"Customer {customer.id}: {customer.name}", file=out)
        elif command == "add-plan" and len(args) == 2:
            plan = storage.add_plan(args[0], int(args[1]))
            print(f"Plan {plan.id}: {plan.name} {format_money(plan.monthly_cents)}/month", file=out)
        elif command == "invoice" and len(args) >= 3:
            items = []
            for text in args[2:]:
                description, _, cents = text.rpartition("=")
                items.append((description, int(cents)))
            invoice = create_invoice(storage, int(args[0]), items, date.fromisoformat(args[1]))
            print(f"Invoice {invoice.id}: {format_money(invoice.total_cents)}", file=out)
        elif command == "report" and not args:
            for month, cents in revenue_by_month(storage).items():
                print(f"{month} {format_money(cents)}", file=out)
        elif command == "statement" and len(args) == 1:
            print(customer_statement(storage, int(args[0])), file=out)
        elif command == "subscribe" and len(args) == 3:
            sub = subscribe(storage, int(args[0]), int(args[1]), date.fromisoformat(args[2]))
            names = (storage.customer(sub.customer_id).name, storage.plan(sub.plan_id).name)
            print(f"Subscription {sub.id}: {names[0]} on {names[1]} from {sub.start.isoformat()}", file=out)
        elif command == "cancel" and len(args) == 2:
            sub = cancel(storage, int(args[0]), date.fromisoformat(args[1]))
            print(f"Subscription {sub.id} ends {sub.end.isoformat()}", file=out)  # type: ignore[union-attr]
        elif command == "bill" and len(args) == 2:
            year_text, _, month_text = args[0].partition("-")
            created = bill_month(storage, int(year_text), int(month_text), date.fromisoformat(args[1]))
            for invoice in created:
                name = storage.customer(invoice.customer_id).name
                print(f"Invoice {invoice.id} for {name}: {format_money(invoice.total_cents)}", file=out)
            if not created:
                print("Nothing to bill.", file=out)
        elif command == "mrr" and len(args) == 1:
            on = date.fromisoformat(args[0])
            print(f"MRR on {on.isoformat()}: {format_money(mrr(storage, on))}", file=out)
        else:
            print(USAGE, file=out)
            return 2
    except (KeyError, ValueError) as error:
        print(f"error: {error}", file=out)
        return 1
    storage.save()
    return 0
