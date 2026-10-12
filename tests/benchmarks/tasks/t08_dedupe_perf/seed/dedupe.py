"""List helpers used by the import job. They are correct but too slow on big inputs."""

from __future__ import annotations

from typing import Any


def find_duplicates(items: list[Any]) -> list[Any]:
    """Return the values that occur more than once, each once, ordered by their first appearance."""
    duplicates: list[Any] = []
    for index, value in enumerate(items):
        if value not in duplicates and value in items[index + 1 :]:
            duplicates.append(value)
    return duplicates


def count_pairs_with_sum(numbers: list[int], target: int) -> int:
    """Count the pairs of positions i < j with numbers[i] + numbers[j] == target."""
    pairs = 0
    for i in range(len(numbers)):
        for j in range(i + 1, len(numbers)):
            if numbers[i] + numbers[j] == target:
                pairs += 1
    return pairs
