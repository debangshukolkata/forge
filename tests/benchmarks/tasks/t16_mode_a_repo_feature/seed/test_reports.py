from __future__ import annotations

from datetime import date

from catalog import Catalog
from cli import run
from loans import LoanService
from members import MemberRegistry
from reports import member_summary, overdue_report


def make_service() -> LoanService:
    catalog, members = Catalog(), MemberRegistry()
    catalog.add("B1", "Emma", 1)
    catalog.add("B2", "Dune", 2)
    members.add("M1", "Ana")
    members.add("M2", "Ben")
    state = {"today": date(2026, 1, 1)}
    service = LoanService(catalog, members, lambda: state["today"])
    service.state = state  # type: ignore[attr-defined]
    return service


def test_overdue_report_orders_by_lateness() -> None:
    service = make_service()
    service.checkout("B2", "M1")
    service.state["today"] = date(2026, 1, 5)  # type: ignore[attr-defined]
    service.checkout("B1", "M2")
    assert overdue_report(service, date(2026, 1, 20)) == ["B2 M1 5d late", "B1 M2 1d late"]
    assert overdue_report(service, date(2026, 1, 15)) == []


def test_member_summary_format() -> None:
    service = make_service()
    assert member_summary(service, "M1") == "Ana (M1): 0 active loans"
    service.checkout("B2", "M1")
    service.checkout("B1", "M1")
    assert member_summary(service, "M1") == "Ana (M1): 2 active loans\n  B1 due 2026-01-15\n  B2 due 2026-01-15"


def test_cli_commands() -> None:
    service = make_service()
    assert run("checkout B1 M1", service) == "Checked out B1 to M1, due 2026-01-15."
    assert run("checkout B1 M2", service).startswith("error:")
    assert run("overdue", service) == "Nothing overdue."
    service.state["today"] = date(2026, 1, 17)  # type: ignore[attr-defined]
    assert run("overdue", service) == "B1 M1 2d late"
    assert run("return B1 M1", service) == "Returned B1. Fine: 0.50."
    assert run("nonsense", service).startswith("commands:")
