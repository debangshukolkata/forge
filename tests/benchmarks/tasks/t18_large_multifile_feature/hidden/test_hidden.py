from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path

import pytest

from billing import bill_month, cancel, subscribe
from cli import main
from invoicing import create_invoice
from models import Subscription
from report import customer_statement, mrr, revenue_by_month
from storage import Storage


def make() -> Storage:
    storage = Storage()
    storage.add_customer("Ana")
    storage.add_customer("Ben")
    storage.add_plan("Pro", 3000)
    storage.add_plan("Lite", 1000)
    return storage


def test_subscription_model_and_storage() -> None:
    storage = make()
    sub = subscribe(storage, 1, 1, date(2026, 1, 10))
    assert isinstance(sub, Subscription) and (sub.id, sub.end) == (1, None)
    assert storage.subscription(1) is sub and storage.subscriptions == {1: sub}
    assert subscribe(storage, 1, 2, date(2026, 1, 10)).id == 2
    with pytest.raises(KeyError):
        storage.subscription(9)
    with pytest.raises(KeyError):
        subscribe(storage, 9, 1, date(2026, 1, 1))
    with pytest.raises(KeyError):
        subscribe(storage, 1, 9, date(2026, 1, 1))


def test_subscribe_overlap_rules() -> None:
    storage = make()
    subscribe(storage, 1, 1, date(2026, 1, 10))
    with pytest.raises(ValueError):
        subscribe(storage, 1, 1, date(2026, 5, 1))  # still running
    assert subscribe(storage, 2, 1, date(2026, 1, 10)).customer_id == 2  # another customer
    cancel(storage, 1, date(2026, 2, 14))
    with pytest.raises(ValueError):
        subscribe(storage, 1, 1, date(2026, 2, 14))  # the end day is still a service day
    assert subscribe(storage, 1, 1, date(2026, 2, 15)).id == 3


def test_cancel_rules() -> None:
    storage = make()
    subscribe(storage, 1, 1, date(2026, 1, 10))
    with pytest.raises(ValueError):
        cancel(storage, 1, date(2026, 1, 9))
    with pytest.raises(KeyError):
        cancel(storage, 5, date(2026, 1, 20))
    assert cancel(storage, 1, date(2026, 1, 10)).end == date(2026, 1, 10)  # one-day subscription
    with pytest.raises(ValueError):
        cancel(storage, 1, date(2026, 1, 20))


def lines(invoice) -> list[tuple[str, int]]:  # type: ignore[no-untyped-def]
    return [(line.description, line.amount_cents) for line in invoice.lines]


def test_full_month_and_invoice_fields() -> None:
    storage = make()
    subscribe(storage, 1, 1, date(2026, 1, 1))
    (invoice,) = bill_month(storage, 2026, 3, date(2026, 3, 31))
    assert lines(invoice) == [("Pro 2026-03", 3000)]
    assert (invoice.customer_id, invoice.issued) == (1, date(2026, 3, 31))
    assert (invoice.period_start, invoice.period_end) == (date(2026, 3, 1), date(2026, 3, 31))
    assert invoice.total_cents == 3000
    assert storage.invoices[invoice.id] is invoice


def test_proration_start_mid_month() -> None:
    storage = make()
    subscribe(storage, 1, 1, date(2026, 2, 19))  # Feb 2026: 28 days, 10 service days
    (invoice,) = bill_month(storage, 2026, 2, date(2026, 2, 28))
    assert lines(invoice) == [("Pro 2026-02 (prorated 10/28 days)", 1071)]  # 1071.43


def test_proration_cancel_mid_month_counts_end_day() -> None:
    storage = make()
    sub = subscribe(storage, 1, 1, date(2026, 1, 1))
    cancel(storage, sub.id, date(2026, 3, 10))
    (invoice,) = bill_month(storage, 2026, 3, date(2026, 3, 31))
    assert lines(invoice) == [("Pro 2026-03 (prorated 10/31 days)", 968)]  # 967.74 -> 968


def test_start_and_end_in_the_same_month() -> None:
    storage = make()
    sub = subscribe(storage, 1, 2, date(2026, 4, 11))
    cancel(storage, sub.id, date(2026, 4, 20))
    (invoice,) = bill_month(storage, 2026, 4, date(2026, 4, 30))
    assert lines(invoice) == [("Lite 2026-04 (prorated 10/30 days)", 333)]


def test_halves_round_up_not_to_even() -> None:
    storage = Storage()
    storage.add_customer("Ana")
    storage.add_plan("Tiny", 5)
    subscribe(storage, 1, 1, date(2026, 4, 16))  # April: 30 days, 15 service days -> 2.5
    (invoice,) = bill_month(storage, 2026, 4, date(2026, 4, 30))
    assert invoice.total_cents == 3
    storage2 = Storage()
    storage2.add_customer("Ana")
    storage2.add_plan("Tiny", 1)
    subscribe(storage2, 1, 1, date(2026, 4, 16))  # 0.5 -> 1
    assert bill_month(storage2, 2026, 4, date(2026, 4, 30))[0].total_cents == 1


def test_leap_february() -> None:
    storage = make()
    subscribe(storage, 1, 1, date(2028, 2, 15))  # 15 of 29 days
    (invoice,) = bill_month(storage, 2028, 2, date(2028, 2, 29))
    assert lines(invoice) == [("Pro 2028-02 (prorated 15/29 days)", 1552)]  # 1551.72
    assert invoice.period_end == date(2028, 2, 29)


def test_not_running_in_the_month_gives_no_line() -> None:
    storage = make()
    early = subscribe(storage, 1, 1, date(2026, 1, 1))
    cancel(storage, early.id, date(2026, 2, 28))  # ends the day before March
    subscribe(storage, 2, 1, date(2026, 4, 1))  # starts the day after March
    assert bill_month(storage, 2026, 3, date(2026, 3, 31)) == []
    assert storage.invoices == {}
    (invoice,) = bill_month(storage, 2026, 4, date(2026, 4, 30))
    assert invoice.customer_id == 2 and invoice.total_cents == 3000


def test_last_day_and_first_day_boundaries() -> None:
    storage = make()
    sub = subscribe(storage, 1, 1, date(2026, 1, 31))  # one day in January
    (invoice,) = bill_month(storage, 2026, 1, date(2026, 1, 31))
    assert lines(invoice) == [("Pro 2026-01 (prorated 1/31 days)", 97)]  # 96.77
    cancel(storage, sub.id, date(2026, 2, 1))  # one day in February
    (invoice,) = bill_month(storage, 2026, 2, date(2026, 2, 28))
    assert lines(invoice) == [("Pro 2026-02 (prorated 1/28 days)", 107)]  # 107.14


def test_one_invoice_per_customer_with_lines_by_subscription_id() -> None:
    storage = make()
    subscribe(storage, 2, 2, date(2026, 1, 1))
    subscribe(storage, 1, 2, date(2026, 1, 1))
    subscribe(storage, 1, 1, date(2026, 1, 1))
    invoices = bill_month(storage, 2026, 5, date(2026, 5, 31))
    assert [i.customer_id for i in invoices] == [1, 2]
    assert lines(invoices[0]) == [("Lite 2026-05", 1000), ("Pro 2026-05", 3000)]
    assert invoices[0].total_cents == 4000 and [i.id for i in invoices] == [1, 2]


def test_running_twice_is_safe_and_new_customers_are_still_billed() -> None:
    storage = make()
    subscribe(storage, 1, 1, date(2026, 1, 1))
    assert len(bill_month(storage, 2026, 5, date(2026, 5, 31))) == 1
    assert bill_month(storage, 2026, 5, date(2026, 6, 1)) == []
    subscribe(storage, 2, 2, date(2026, 5, 1))
    again = bill_month(storage, 2026, 5, date(2026, 6, 1))
    assert [i.customer_id for i in again] == [2]
    assert len(storage.invoices) == 2
    assert len(bill_month(storage, 2026, 6, date(2026, 6, 30))) == 2  # another month is a new run


def test_a_one_off_invoice_does_not_block_billing() -> None:
    storage = make()
    subscribe(storage, 1, 1, date(2026, 1, 1))
    create_invoice(storage, 1, [("Setup", 500)], date(2026, 5, 2))
    assert len(bill_month(storage, 2026, 5, date(2026, 5, 31))) == 1


def test_free_plan_still_gets_an_invoice() -> None:
    storage = Storage()
    storage.add_customer("Ana")
    storage.add_plan("Free", 0)
    subscribe(storage, 1, 1, date(2026, 1, 1))
    (invoice,) = bill_month(storage, 2026, 1, date(2026, 1, 31))
    assert lines(invoice) == [("Free 2026-01", 0)] and invoice.total_cents == 0


def test_bad_month() -> None:
    storage = make()
    for month in (0, 13):
        with pytest.raises(ValueError):
            bill_month(storage, 2026, month, date(2026, 1, 1))


def test_revenue_by_month_counts_recurring_invoices_by_issue_month() -> None:
    storage = make()
    subscribe(storage, 1, 1, date(2026, 1, 1))
    bill_month(storage, 2026, 1, date(2026, 2, 1))
    bill_month(storage, 2026, 2, date(2026, 2, 28))
    assert revenue_by_month(storage) == {"2026-02": 6000}


def test_mrr() -> None:
    storage = make()
    subscribe(storage, 1, 1, date(2026, 1, 10))
    sub = subscribe(storage, 2, 2, date(2026, 2, 1))
    cancel(storage, sub.id, date(2026, 2, 28))
    assert mrr(storage, date(2026, 1, 9)) == 0
    assert mrr(storage, date(2026, 1, 10)) == 3000
    assert mrr(storage, date(2026, 2, 1)) == 4000
    assert mrr(storage, date(2026, 2, 28)) == 4000
    assert mrr(storage, date(2026, 3, 1)) == 3000


def test_statement() -> None:
    storage = make()
    assert customer_statement(storage, 2) == "Statement for Ben (#2)"
    sub = subscribe(storage, 1, 2, date(2026, 1, 10))
    subscribe(storage, 1, 1, date(2026, 3, 1))
    create_invoice(storage, 1, [("Setup", 500)], date(2026, 1, 12))
    assert customer_statement(storage, 1) == (
        "Statement for Ana (#1)\n  #1 2026-01-12 5.00\nSubscriptions:\n  #1 Lite since 2026-01-10\n  #2 Pro since 2026-03-01"
    )
    cancel(storage, sub.id, date(2026, 2, 14))
    assert customer_statement(storage, 1).splitlines()[3] == "  #1 Lite 2026-01-10..2026-02-14"


def test_persistence_format_and_old_files(tmp_path: Path) -> None:
    path = tmp_path / "store.json"
    storage = Storage(path)
    storage.add_customer("Ana")
    storage.add_plan("Pro", 3000)
    subscribe(storage, 1, 1, date(2026, 1, 10))
    cancel(storage, 1, date(2026, 2, 14))
    subscribe(storage, 1, 1, date(2026, 3, 1))
    bill_month(storage, 2026, 3, date(2026, 3, 31))
    storage.save()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["next_id"] == {"customer": 2, "plan": 2, "invoice": 2}
    assert data["subscriptions"] == [
        {"id": 1, "customer_id": 1, "plan_id": 1, "start": "2026-01-10", "end": "2026-02-14"},
        {"id": 2, "customer_id": 1, "plan_id": 1, "start": "2026-03-01", "end": None},
    ]
    assert data["invoices"][0]["period_start"] == "2026-03-01" and data["invoices"][0]["period_end"] == "2026-03-31"
    again = Storage(path)
    assert again.subscriptions[1].end == date(2026, 2, 14) and again.subscriptions[2].end is None
    assert len(bill_month(again, 2026, 3, date(2026, 4, 1))) == 0  # the saved invoice is remembered
    again.add_plan("Lite", 1000)
    assert again.add_subscription(1, 2, date(2026, 4, 1)).id == 3


def test_old_file_without_subscriptions_loads(tmp_path: Path) -> None:
    path = tmp_path / "old.json"
    path.write_text(
        json.dumps(
            {
                "next_id": {"customer": 2, "plan": 2, "invoice": 2},
                "customers": [{"id": 1, "name": "Ana"}],
                "plans": [{"id": 1, "name": "Pro", "monthly_cents": 3000}],
                "invoices": [
                    {
                        "id": 1,
                        "customer_id": 1,
                        "issued": "2026-01-31",
                        "period_start": None,
                        "period_end": None,
                        "lines": [{"description": "Setup", "amount_cents": 500}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    storage = Storage(path)
    assert storage.subscriptions == {}
    assert storage.invoices[1].total_cents == 500
    assert subscribe(storage, 1, 1, date(2026, 2, 1)).id == 1
    assert storage.add_customer("Ben").id == 2


def test_cli_end_to_end(tmp_path: Path) -> None:
    path = tmp_path / "store.json"
    out = io.StringIO()
    for argv in (
        ["add-customer", "Ana"],
        ["add-plan", "Pro", "3000"],
        ["subscribe", "1", "1", "2026-02-19"],
        ["bill", "2026-02", "2026-02-28"],
        ["bill", "2026-02", "2026-02-28"],
        ["mrr", "2026-03-01"],
        ["cancel", "1", "2026-03-10"],
        ["mrr", "2026-03-11"],
        ["statement", "1"],
    ):
        assert main(argv, path, out) == 0, argv
    text = out.getvalue().splitlines()
    assert "Subscription 1: Ana on Pro from 2026-02-19" in text
    assert "Invoice 1 for Ana: 10.71" in text
    assert text.count("Nothing to bill.") == 1
    assert "MRR on 2026-03-01: 30.00" in text and "MRR on 2026-03-11: 0.00" in text
    assert "Subscription 1 ends 2026-03-10" in text
    assert text[-3:] == ["Statement for Ana (#1)", "  #1 2026-02-28 10.71", "Subscriptions:", "  #1 Pro 2026-02-19..2026-03-10"][-3:]
    assert "  #1 Pro 2026-02-19..2026-03-10" in text


def test_cli_errors_save_nothing_and_usage(tmp_path: Path) -> None:
    path = tmp_path / "store.json"
    out = io.StringIO()
    main(["add-customer", "Ana"], path, out)
    main(["add-plan", "Pro", "3000"], path, out)
    before = path.read_text(encoding="utf-8")
    for argv in (
        ["subscribe", "9", "1", "2026-01-01"],
        ["subscribe", "1", "1", "not-a-date"],
        ["cancel", "5", "2026-01-01"],
        ["bill", "2026-13", "2026-01-31"],
        ["bill", "garbage", "2026-01-31"],
        ["mrr", "2026-99-01"],
    ):
        assert main(argv, path, out) == 1, argv
    assert path.read_text(encoding="utf-8") == before
    assert out.getvalue().count("error:") == 6
    out = io.StringIO()
    assert main(["bill"], path, out) == 2
    usage = out.getvalue().strip()
    assert usage.startswith("usage: add-customer NAME | add-plan NAME CENTS")
    assert usage.endswith("| subscribe CUSTOMER PLAN START | cancel SUBSCRIPTION END | bill YYYY-MM ISSUED | mrr DATE")


def test_cli_nothing_to_bill_when_there_are_no_subscriptions(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    out = io.StringIO()
    main(["add-customer", "Ana"], path, out)
    out = io.StringIO()
    assert main(["bill", "2026-05", "2026-05-31"], path, out) == 0
    assert out.getvalue() == "Nothing to bill.\n"
