"""Checking books out and in."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

from catalog import Catalog
from fines import fine_for
from members import MemberRegistry
from models import Loan

LOAN_DAYS = 14
MAX_ACTIVE_LOANS = 3


class LoanError(Exception):
    """A request the library rules do not allow."""


class LoanService:
    def __init__(self, catalog: Catalog, members: MemberRegistry, clock: Callable[[], date] = date.today) -> None:
        self.catalog = catalog
        self.members = members
        self.clock = clock
        self.loans: list[Loan] = []

    def active_loans(self, *, book_id: str | None = None, member_id: str | None = None) -> list[Loan]:
        return [
            loan
            for loan in self.loans
            if loan.returned is None
            and (book_id is None or loan.book_id == book_id)
            and (member_id is None or loan.member_id == member_id)
        ]

    def free_copies(self, book_id: str) -> int:
        return self.catalog.get(book_id).copies - len(self.active_loans(book_id=book_id))

    def checkout(self, book_id: str, member_id: str) -> Loan:
        self.catalog.get(book_id)
        self.members.get(member_id)
        if self.active_loans(book_id=book_id, member_id=member_id):
            raise LoanError(f"{member_id} already has {book_id}")
        if len(self.active_loans(member_id=member_id)) >= MAX_ACTIVE_LOANS:
            raise LoanError(f"{member_id} has reached the limit of {MAX_ACTIVE_LOANS} loans")
        if self.free_copies(book_id) <= 0:
            raise LoanError(f"no copy of {book_id} is available")
        loan = Loan(book_id, member_id, self.clock() + timedelta(days=LOAN_DAYS))
        self.loans.append(loan)
        return loan

    def return_book(self, book_id: str, member_id: str) -> int:
        """Hand a book back; returns the fine in cents."""
        for loan in self.active_loans(book_id=book_id, member_id=member_id):
            loan.returned = self.clock()
            return fine_for(loan.due, loan.returned)
        raise LoanError(f"{member_id} does not have {book_id}")
