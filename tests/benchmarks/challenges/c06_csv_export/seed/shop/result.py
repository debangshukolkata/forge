"""Operations in this package never raise for expected problems: they return a Result."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Result(Generic[T]):
    value: T | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @staticmethod
    def success(value: T) -> Result[T]:
        return Result(value=value)

    @staticmethod
    def failure(message: str) -> Result[T]:
        return Result(error=message)
