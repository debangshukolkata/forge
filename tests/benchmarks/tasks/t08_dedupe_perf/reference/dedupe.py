"""List helpers used by the import job."""

from __future__ import annotations

from collections import Counter
from typing import Any


def find_duplicates(items: list[Any]) -> list[Any]:
    """Return the values that occur more than once, each once, ordered by their first appearance."""
    counts = Counter(items)
    seen: set[Any] = set()
    duplicates: list[Any] = []
    for value in items:
        if counts[value] > 1 and value not in seen:
            seen.add(value)
            duplicates.append(value)
    return duplicates


def count_pairs_with_sum(numbers: list[int], target: int) -> int:
    """Count the pairs of positions i < j with numbers[i] + numbers[j] == target."""
    seen: Counter[int] = Counter()
    pairs = 0
    for value in numbers:
        pairs += seen[target - value]
        seen[value] += 1
    return pairs
