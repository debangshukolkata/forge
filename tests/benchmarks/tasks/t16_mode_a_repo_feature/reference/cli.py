"""A tiny command interpreter for the loan desk: `run("checkout B1 M1", service)` returns the text to print."""

from __future__ import annotations

from loans import LoanError, LoanService
from reports import holds_report, member_summary, overdue_report

USAGE = (
    "commands: checkout BOOK MEMBER | return BOOK MEMBER | overdue | summary MEMBER"
    " | reserve BOOK MEMBER | cancel BOOK MEMBER | holds"
)


def run(line: str, service: LoanService) -> str:
    words = line.split()
    if not words:
        return USAGE
    command, args = words[0], words[1:]
    try:
        if command == "checkout" and len(args) == 2:
            loan = service.checkout(args[0], args[1])
            return f"Checked out {loan.book_id} to {loan.member_id}, due {loan.due.isoformat()}."
        if command == "return" and len(args) == 2:
            fine = service.return_book(args[0], args[1])
            return f"Returned {args[0]}." + (f" Fine: {fine / 100:.2f}." if fine else "")
        if command == "overdue" and not args:
            lines = overdue_report(service, service.clock())
            return "\n".join(lines) if lines else "Nothing overdue."
        if command == "summary" and len(args) == 1:
            return member_summary(service, args[0])
        if command == "reserve" and len(args) == 2:
            position = service.reserve(args[0], args[1])
            return f"Reserved {args[0]} for {args[1]} (position {position})."
        if command == "cancel" and len(args) == 2:
            if service.cancel_reservation(args[0], args[1]):
                return f"Cancelled hold on {args[0]} for {args[1]}."
            return f"No hold on {args[0]} for {args[1]}."
        if command == "holds" and not args:
            lines = holds_report(service)
            return "\n".join(lines) if lines else "No holds."
    except (KeyError, LoanError, ValueError) as error:
        return f"error: {error}"
    return USAGE
