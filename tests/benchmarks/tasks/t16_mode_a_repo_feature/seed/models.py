"""Plain data records of the library."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class Book:
    id: str
    title: str
    copies: int


@dataclass
class Member:
    id: str
    name: str


@dataclass
class Loan:
    book_id: str
    member_id: str
    due: date
    returned: date | None = None
