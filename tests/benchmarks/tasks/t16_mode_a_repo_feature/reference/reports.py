"""Text reports for the desk."""

from __future__ import annotations

from datetime import date

from loans import LoanService


def overdue_report(service: LoanService, today: date) -> list[str]:
    """One line per overdue loan, the most late first, then by book id."""
    rows = [
        ((today - loan.due).days, loan.book_id, loan.member_id)
        for loan in service.active_loans()
        if loan.due < today
    ]
    rows.sort(key=lambda row: (-row[0], row[1], row[2]))
    return [f"{book} {member} {days}d late" for days, book, member in rows]


def holds_report(service: LoanService) -> list[str]:
    lines = []
    for book in service.catalog.all():
        queue = service.reservations(book.id)
        if queue:
            lines.append(f"{book.id}: {', '.join(queue)}")
    return lines


def member_summary(service: LoanService, member_id: str) -> str:
    member = service.members.get(member_id)
    loans = sorted(service.active_loans(member_id=member_id), key=lambda loan: (loan.due, loan.book_id))
    holds = []
    for book in service.catalog.all():
        queue = service.reservations(book.id)
        if member_id in queue:
            holds.append(f"  hold {book.id} (position {queue.index(member_id) + 1})")
    header = f"{member.name} ({member.id}): {len(loans)} active loans"
    if holds:
        header += f", {len(holds)} hold" + ("" if len(holds) == 1 else "s")
    lines = [header]
    lines += [f"  {loan.book_id} due {loan.due.isoformat()}" for loan in loans]
    return "\n".join(lines + holds)
