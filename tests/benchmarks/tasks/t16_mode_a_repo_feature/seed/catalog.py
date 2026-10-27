"""The books the library owns."""

from __future__ import annotations

from models import Book


class Catalog:
    def __init__(self) -> None:
        self._books: dict[str, Book] = {}

    def add(self, book_id: str, title: str, copies: int = 1) -> Book:
        if book_id in self._books:
            raise ValueError(f"book {book_id} already exists")
        if copies < 1:
            raise ValueError("a book needs at least one copy")
        book = Book(book_id, title, copies)
        self._books[book_id] = book
        return book

    def get(self, book_id: str) -> Book:
        return self._books[book_id]  # KeyError for an unknown book

    def all(self) -> list[Book]:
        return [self._books[key] for key in sorted(self._books)]
