from __future__ import annotations

from datetime import date

import pytest

from catalog import Catalog
from cli import run
from loans import CopyReservedError, LoanError, LoanService
from members import MemberRegistry
from reports import holds_report, member_summary


def make_service() -> LoanService:
    catalog, members = Catalog(), MemberRegistry()
    catalog.add("B1", "Emma", 1)
    catalog.add("B2", "Dune", 2)
    catalog.add("B3", "Ulysses", 1)
    catalog.add("B4", "Walden", 1)
    for number, name in enumerate(["Ana", "Ben", "Cy", "Di", "Eve"], start=1):
        members.add(f"M{number}", name)
    return LoanService(catalog, members, lambda: date(2026, 3, 1))


def test_copy_reserved_error_is_a_loan_error() -> None:
    assert issubclass(CopyReservedError, LoanError)


def test_reserve_returns_positions_and_requires_no_free_copy() -> None:
    service = make_service()
    with pytest.raises(LoanError):
        service.reserve("B1", "M2")  # a copy is free: just check it out
    service.checkout("B1", "M1")
    assert service.reserve("B1", "M2") == 1
    assert service.reserve("B1", "M3") == 2
    assert service.reservations("B1") == ["M2", "M3"]


def test_reserve_errors() -> None:
    service = make_service()
    service.checkout("B1", "M1")
    with pytest.raises(LoanError):
        service.reserve("B1", "M1")  # already has it
    service.reserve("B1", "M2")
    with pytest.raises(LoanError):
        service.reserve("B1", "M2")  # already queued
    with pytest.raises(KeyError):
        service.reserve("B9", "M2")
    with pytest.raises(KeyError):
        service.reserve("B1", "M9")
    with pytest.raises(KeyError):
        service.reservations("B9")
    assert service.reservations("B2") == []


def test_reservations_returns_a_copy() -> None:
    service = make_service()
    service.checkout("B1", "M1")
    service.reserve("B1", "M2")
    service.reservations("B1").clear()
    assert service.reservations("B1") == ["M2"]


def test_free_copy_is_promised_to_the_queue() -> None:
    service = make_service()
    service.checkout("B1", "M1")
    service.reserve("B1", "M2")
    service.reserve("B1", "M3")
    service.return_book("B1", "M1")
    with pytest.raises(CopyReservedError):
        service.checkout("B1", "M4")  # not queued
    with pytest.raises(CopyReservedError):
        service.checkout("B1", "M3")  # queued, but second
    loan = service.checkout("B1", "M2")
    assert loan.member_id == "M2"
    assert service.reservations("B1") == ["M3"]
    service.return_book("B1", "M2")
    assert service.checkout("B1", "M3").member_id == "M3"
    assert service.reservations("B1") == []


def test_checkout_without_any_free_copy_is_a_plain_loan_error() -> None:
    service = make_service()
    service.checkout("B1", "M1")
    service.reserve("B1", "M2")
    with pytest.raises(LoanError) as raised:
        service.checkout("B1", "M2")
    assert not isinstance(raised.value, CopyReservedError)


def test_two_copies_serve_two_queue_members() -> None:
    service = make_service()
    service.checkout("B2", "M1")
    service.checkout("B2", "M2")
    assert [service.reserve("B2", m) for m in ("M3", "M4", "M5")] == [1, 2, 3]
    service.return_book("B2", "M1")
    service.return_book("B2", "M2")
    with pytest.raises(CopyReservedError):
        service.checkout("B2", "M5")
    service.checkout("B2", "M4")  # index 1 < 2 free copies
    assert service.reservations("B2") == ["M3", "M5"]
    service.checkout("B2", "M3")
    assert service.reservations("B2") == ["M5"]
    with pytest.raises(LoanError):
        service.checkout("B2", "M5")  # no free copy left


def test_non_queued_member_can_take_a_surplus_copy() -> None:
    service = make_service()
    service.checkout("B2", "M1")
    service.checkout("B2", "M2")
    service.reserve("B2", "M3")
    service.return_book("B2", "M1")
    service.return_book("B2", "M2")  # two free copies, one queued member
    assert service.checkout("B2", "M4").member_id == "M4"  # free 2 > queue 1
    with pytest.raises(CopyReservedError):
        service.checkout("B2", "M5")  # free 1 is not > queue 1
    assert service.checkout("B2", "M3").member_id == "M3"


def test_cannot_reserve_when_a_copy_is_free_and_not_promised_to_others() -> None:
    service = make_service()
    service.checkout("B2", "M1")
    service.checkout("B2", "M2")
    service.reserve("B2", "M3")
    service.return_book("B2", "M1")
    service.return_book("B2", "M2")
    with pytest.raises(LoanError):
        service.reserve("B2", "M4")  # free 2 > queue 1: available
    service.checkout("B2", "M3")
    service.checkout("B2", "M4")
    service.reserve("B2", "M5")  # no copy free any more


def test_front_of_queue_member_at_the_limit_keeps_their_place() -> None:
    service = make_service()
    service.catalog.add("B5", "Ivanhoe", 1)
    service.checkout("B1", "M2")
    service.reserve("B1", "M1")
    service.checkout("B2", "M1")
    service.checkout("B3", "M1")
    service.checkout("B4", "M1")
    service.return_book("B1", "M2")
    with pytest.raises(LoanError) as raised:
        service.checkout("B1", "M1")
    assert "limit" in str(raised.value)
    assert service.reservations("B1") == ["M1"]
    service.return_book("B4", "M1")
    service.checkout("B1", "M1")
    assert service.reservations("B1") == []


def test_cancel_reservation() -> None:
    service = make_service()
    service.checkout("B1", "M1")
    service.reserve("B1", "M2")
    service.reserve("B1", "M3")
    assert service.cancel_reservation("B1", "M2") is True
    assert service.cancel_reservation("B1", "M2") is False
    assert service.cancel_reservation("B3", "M2") is False
    assert service.reservations("B1") == ["M3"]
    assert service.reserve("B1", "M2") == 2


def test_cancelled_front_member_releases_the_copy_to_the_next() -> None:
    service = make_service()
    service.checkout("B1", "M1")
    service.reserve("B1", "M2")
    service.reserve("B1", "M3")
    service.return_book("B1", "M1")
    service.cancel_reservation("B1", "M2")
    assert service.checkout("B1", "M3").member_id == "M3"


def test_holds_report() -> None:
    service = make_service()
    assert holds_report(service) == []
    service.checkout("B3", "M1")
    service.checkout("B1", "M1")
    service.reserve("B3", "M4")
    service.reserve("B1", "M3")
    service.reserve("B1", "M2")
    assert holds_report(service) == ["B1: M3, M2", "B3: M4"]


def test_member_summary_with_and_without_holds() -> None:
    service = make_service()
    service.checkout("B1", "M1")
    service.checkout("B3", "M1")
    assert member_summary(service, "M2") == "Ben (M2): 0 active loans"
    service.reserve("B3", "M2")
    assert member_summary(service, "M2") == "Ben (M2): 0 active loans, 1 hold\n  hold B3 (position 1)"
    service.reserve("B1", "M3")
    service.reserve("B1", "M2")
    assert member_summary(service, "M2") == (
        "Ben (M2): 0 active loans, 2 holds\n  hold B1 (position 2)\n  hold B3 (position 1)"
    )
    assert member_summary(service, "M1") == "Ana (M1): 2 active loans\n  B1 due 2026-03-15\n  B3 due 2026-03-15"


def test_member_summary_loans_come_before_holds() -> None:
    service = make_service()
    service.checkout("B1", "M2")
    service.checkout("B3", "M1")
    service.reserve("B1", "M1")
    assert member_summary(service, "M1") == "Ana (M1): 1 active loans, 1 hold\n  B3 due 2026-03-15\n  hold B1 (position 1)"


def test_cli_reserve_cancel_holds() -> None:
    service = make_service()
    assert run("holds", service) == "No holds."
    run("checkout B1 M1", service)
    assert run("reserve B1 M2", service) == "Reserved B1 for M2 (position 1)."
    assert run("reserve B1 M3", service) == "Reserved B1 for M3 (position 2)."
    assert run("holds", service) == "B1: M2, M3"
    assert run("cancel B1 M2", service) == "Cancelled hold on B1 for M2."
    assert run("cancel B1 M2", service) == "No hold on B1 for M2."
    assert run("reserve B1 M3", service).startswith("error:")
    assert run("reserve B9 M3", service).startswith("error:")
    assert run("reserve B1", service).startswith("commands:")


def test_cli_checkout_reserved_copy_is_an_error_line() -> None:
    service = make_service()
    run("checkout B1 M1", service)
    run("reserve B1 M2", service)
    run("return B1 M1", service)
    assert run("checkout B1 M3", service).startswith("error:")
    assert run("checkout B1 M2", service) == "Checked out B1 to M2, due 2026-03-15."


def test_usage_lists_the_new_commands() -> None:
    usage = run("", make_service())
    assert usage.endswith("| summary MEMBER | reserve BOOK MEMBER | cancel BOOK MEMBER | holds")
    assert usage.startswith("commands: checkout BOOK MEMBER | return BOOK MEMBER | overdue")
