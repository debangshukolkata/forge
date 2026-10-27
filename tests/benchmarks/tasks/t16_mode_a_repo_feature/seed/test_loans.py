from __future__ import annotations

from datetime import date, timedelta

import pytest

from catalog import Catalog
from fines import fine_for
from loans import LoanError, LoanService
from members import MemberRegistry


class Clock:
    def __init__(self, today: date) -> None:
        self.today = today

    def __call__(self) -> date:
        return self.today


def make_service() -> tuple[LoanService, Clock]:
    catalog, members = Catalog(), MemberRegistry()
    catalog.add("B1", "Emma", 1)
    catalog.add("B2", "Dune", 2)
    for number, name in enumerate(["Ana", "Ben", "Cy", "Di"], start=1):
        members.add(f"M{number}", name)
    clock = Clock(date(2026, 1, 1))
    return LoanService(catalog, members, clock), clock


def test_checkout_sets_due_date_and_uses_a_copy() -> None:
    service, _ = make_service()
    loan = service.checkout("B1", "M1")
    assert loan.due == date(2026, 1, 15)
    assert service.free_copies("B1") == 0
    with pytest.raises(LoanError):
        service.checkout("B1", "M2")


def test_member_limit_and_duplicate_loan() -> None:
    service, _ = make_service()
    service.catalog.add("B3", "Ulysses", 1)
    service.catalog.add("B4", "Walden", 1)
    service.checkout("B2", "M1")
    with pytest.raises(LoanError):
        service.checkout("B2", "M1")
    service.checkout("B1", "M1")
    service.checkout("B3", "M1")
    with pytest.raises(LoanError):
        service.checkout("B4", "M1")


def test_unknown_ids() -> None:
    service, _ = make_service()
    with pytest.raises(KeyError):
        service.checkout("B9", "M1")
    with pytest.raises(KeyError):
        service.checkout("B1", "M9")


def test_return_and_fine() -> None:
    service, clock = make_service()
    service.checkout("B1", "M1")
    clock.today = date(2026, 1, 15) + timedelta(days=4)
    assert service.return_book("B1", "M1") == 100
    assert service.free_copies("B1") == 1
    with pytest.raises(LoanError):
        service.return_book("B1", "M1")


def test_fine_for_on_time_is_zero() -> None:
    assert fine_for(date(2026, 1, 15), date(2026, 1, 15)) == 0
    assert fine_for(date(2026, 1, 15), date(2026, 1, 10)) == 0
