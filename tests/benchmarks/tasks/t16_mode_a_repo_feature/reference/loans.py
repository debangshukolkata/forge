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


class CopyReservedError(LoanError):
    """A copy is free but promised to members who reserved the book first."""


class LoanService:
    def __init__(self, catalog: Catalog, members: MemberRegistry, clock: Callable[[], date] = date.today) -> None:
        self.catalog = catalog
        self.members = members
        self.clock = clock
        self.loans: list[Loan] = []
        self._queues: dict[str, list[str]] = {}

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

    def reservations(self, book_id: str) -> list[str]:
        self.catalog.get(book_id)
        return list(self._queues.get(book_id, []))

    def _may_take(self, book_id: str, member_id: str) -> bool:
        """Free copies go to the queue first (first come, first served)."""
        free = self.free_copies(book_id)
        queue = self._queues.get(book_id, [])
        if free <= 0:
            return False
        if member_id in queue:
            return queue.index(member_id) < free
        return free > len(queue)

    def reserve(self, book_id: str, member_id: str) -> int:
        self.catalog.get(book_id)
        self.members.get(member_id)
        queue = self._queues.setdefault(book_id, [])
        if self.active_loans(book_id=book_id, member_id=member_id):
            raise LoanError(f"{member_id} already has {book_id}")
        if member_id in queue:
            raise LoanError(f"{member_id} already reserved {book_id}")
        if self._may_take(book_id, member_id):
            raise LoanError(f"{book_id} is available: check it out instead")
        queue.append(member_id)
        return len(queue)

    def cancel_reservation(self, book_id: str, member_id: str) -> bool:
        queue = self._queues.get(book_id, [])
        if member_id in queue:
            queue.remove(member_id)
            return True
        return False

    def checkout(self, book_id: str, member_id: str) -> Loan:
        self.catalog.get(book_id)
        self.members.get(member_id)
        if self.active_loans(book_id=book_id, member_id=member_id):
            raise LoanError(f"{member_id} already has {book_id}")
        if len(self.active_loans(member_id=member_id)) >= MAX_ACTIVE_LOANS:
            raise LoanError(f"{member_id} has reached the limit of {MAX_ACTIVE_LOANS} loans")
        if self.free_copies(book_id) <= 0:
            raise LoanError(f"no copy of {book_id} is available")
        if not self._may_take(book_id, member_id):
            raise CopyReservedError(f"the free copy of {book_id} is reserved for other members")
        self.cancel_reservation(book_id, member_id)
        loan = Loan(book_id, member_id, self.clock() + timedelta(days=LOAN_DAYS))
        self.loans.append(loan)
        return loan

    def return_book(self, book_id: str, member_id: str) -> int:
        """Hand a book back; returns the fine in cents."""
        for loan in self.active_loans(book_id=book_id, member_id=member_id):
            loan.returned = self.clock()
            return fine_for(loan.due, loan.returned)
        raise LoanError(f"{member_id} does not have {book_id}")
