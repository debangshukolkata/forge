"""Command line: `main(["add-customer", "Ana"], store_path)`. Prints through `out`; returns the exit code."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from typing import TextIO

from invoicing import create_invoice
from report import customer_statement, format_money, revenue_by_month
from storage import Storage

USAGE = "usage: add-customer NAME | add-plan NAME CENTS | invoice CUSTOMER DATE DESCRIPTION=CENTS... | report | statement CUSTOMER"


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
        else:
            print(USAGE, file=out)
            return 2
    except (KeyError, ValueError) as error:
        print(f"error: {error}", file=out)
        return 1
    storage.save()
    return 0
