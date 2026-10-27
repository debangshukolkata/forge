from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path

import pytest

from cli import main
from invoicing import create_invoice
from storage import Storage


def test_create_invoice_and_total() -> None:
    storage = Storage()
    customer = storage.add_customer(" Ana ")
    invoice = create_invoice(storage, customer.id, [("Setup", 500), ("Hosting", 1250)], date(2026, 1, 31))
    assert (customer.name, invoice.id, invoice.total_cents) == ("Ana", 1, 1750)
    assert storage.invoices_for(customer.id) == [invoice]


def test_errors() -> None:
    storage = Storage()
    with pytest.raises(KeyError):
        create_invoice(storage, 9, [("x", 1)], date(2026, 1, 1))
    customer = storage.add_customer("Ana")
    with pytest.raises(ValueError):
        create_invoice(storage, customer.id, [], date(2026, 1, 1))
    with pytest.raises(ValueError):
        storage.add_plan("Free", -1)


def test_file_round_trip_keeps_the_documented_format(tmp_path: Path) -> None:
    path = tmp_path / "store.json"
    storage = Storage(path)
    customer = storage.add_customer("Ana")
    storage.add_plan("Pro", 3000)
    create_invoice(storage, customer.id, [("Setup", 500)], date(2026, 1, 31))
    storage.save()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["next_id"] == {"customer": 2, "plan": 2, "invoice": 2}
    assert data["invoices"][0]["lines"] == [{"description": "Setup", "amount_cents": 500}]
    again = Storage(path)
    assert again.invoices[1].total_cents == 500 and again.plans[1].monthly_cents == 3000
    assert again.add_customer("Ben").id == 2


def test_cli_flow(tmp_path: Path) -> None:
    path = tmp_path / "store.json"
    out = io.StringIO()
    assert main(["add-customer", "Ana"], path, out) == 0
    assert main(["invoice", "1", "2026-02-10", "Setup=500", "Per diem=1250"], path, out) == 0
    assert main(["invoice", "7", "2026-02-10", "x=1"], path, out) == 1
    assert main(["report"], path, out) == 0
    assert main(["statement", "1"], path, out) == 0
    assert main([], path, out) == 2
    text = out.getvalue()
    assert "Invoice 1: 17.50" in text and "error:" in text and "2026-02 17.50" in text
    assert "  #1 2026-02-10 17.50" in text
