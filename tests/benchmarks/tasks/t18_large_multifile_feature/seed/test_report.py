from __future__ import annotations

from datetime import date

from invoicing import create_invoice
from report import customer_statement, format_money, revenue_by_month
from storage import Storage


def test_format_money() -> None:
    assert [format_money(c) for c in (0, 5, 100, 1234, -250)] == ["0.00", "0.05", "1.00", "12.34", "-2.50"]


def test_revenue_by_month_groups_by_issue_month() -> None:
    storage = Storage()
    ana = storage.add_customer("Ana")
    create_invoice(storage, ana.id, [("a", 100)], date(2026, 2, 3))
    create_invoice(storage, ana.id, [("b", 200)], date(2026, 1, 30))
    create_invoice(storage, ana.id, [("c", 50)], date(2026, 2, 28))
    assert revenue_by_month(storage) == {"2026-01": 200, "2026-02": 150}


def test_statement_lists_invoices() -> None:
    storage = Storage()
    ana = storage.add_customer("Ana")
    create_invoice(storage, ana.id, [("a", 100)], date(2026, 2, 3))
    assert customer_statement(storage, ana.id) == "Statement for Ana (#1)\n  #1 2026-02-03 1.00"
