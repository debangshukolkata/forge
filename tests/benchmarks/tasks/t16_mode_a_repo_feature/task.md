The folder is a small library-desk program: `models.py`, `catalog.py`, `members.py`, `fines.py`, `loans.py`, `reports.py`, `cli.py`, and three test files. Read it first, keep its style, and keep every existing test passing. Add **reservations (holds with a waiting list)**. The work touches `loans.py`, `reports.py` and `cli.py`; put a record type in `models.py` if you want one.

**Loans (`loans.py`)**
- Each book has a first-come-first-served queue of member ids.
- `LoanService.reserve(book_id, member_id) -> int` puts the member at the end of the queue and returns the 1-based position. Unknown book or member: `KeyError` (as everywhere else). `LoanError` if the member already has that book on loan, is already in its queue, or could simply check the book out right now (see the next rule).
- Free copies are first promised to the queue. A member may check a book out only if `free_copies > 0` and either (a) they are in the queue at 0-based index `i` with `i < free_copies`, or (b) they are not in the queue and `free_copies > len(queue)`. A successful checkout removes the member from that book's queue (the others move up).
- `checkout` keeps its current order of checks (unknown ids, already has the book, member limit) and then: no free copy raises `LoanError` as before; a free copy that is promised to other members raises a new `CopyReservedError`, a subclass of `LoanError` defined in `loans.py`. A member who is at the front of a queue but is at the loan limit still gets the limit `LoanError` and keeps their place.
- `cancel_reservation(book_id, member_id) -> bool` removes the member from the queue and returns `True`, or returns `False` if they were not in it. `reservations(book_id) -> list[str]` returns a copy of the queue (member ids in order); it is empty for a book nobody reserved, and raises `KeyError` for an unknown book.

**Reports (`reports.py`)**
- New `holds_report(service) -> list[str]`: for each book with a non-empty queue, in book id order, one line `"<book id>: <member id>, <member id>"` (queue order, separated by comma and space).
- `member_summary` stays exactly as it is for a member with no holds. For a member with holds the header gets `, 1 hold` or `, 2 holds` (and so on) appended after the loan count, and after the loan lines come one line per hold, ordered by book id: `"  hold <book id> (position <n>)"` with the 1-based position.

**CLI (`cli.py`)**
- `reserve BOOK MEMBER` prints `Reserved <book> for <member> (position <n>).`
- `cancel BOOK MEMBER` prints `Cancelled hold on <book> for <member>.` or `No hold on <book> for <member>.`
- `holds` prints the lines of `holds_report` joined by newlines, or `No holds.` when there are none.
- Errors print `error: ...` like the other commands, and the usage text lists the new commands after the existing ones, in the order `reserve BOOK MEMBER | cancel BOOK MEMBER | holds`, with the same ` | ` separator.

Add tests for the new behaviour in a new file `test_reservations.py`.
