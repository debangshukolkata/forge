"""Okapi BM25 ranking in plain Python (DECISIONS D-058: avoids rank_bm25, which pulls in numpy)."""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[A-Za-z0-9]+")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def tokenize(text: str) -> list[str]:
    """Lower-case words; identifiers are also split:
    ClaimsService -> claims, service; get_claim -> get, claim."""
    words: list[str] = []
    for raw in _TOKEN.findall(text):
        words.append(raw.lower())
        parts = [p for chunk in raw.split("_") for p in _CAMEL.split(chunk) if p]
        if len(parts) > 1:
            words.extend(p.lower() for p in parts)
    return words


class BM25:
    def __init__(self, documents: list[list[str]], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.frequencies = [Counter(doc) for doc in documents]
        self.lengths = [len(doc) for doc in documents]
        self.average_length = sum(self.lengths) / len(documents) if documents else 0.0
        containing: Counter[str] = Counter()
        for frequency in self.frequencies:
            containing.update(frequency.keys())
        count = len(documents)
        self.idf = {term: math.log(1 + (count - n + 0.5) / (n + 0.5)) for term, n in containing.items()}

    def scores(self, query: list[str]) -> list[float]:
        results = []
        for frequency, length in zip(self.frequencies, self.lengths, strict=True):
            score = 0.0
            for term in query:
                if term not in frequency:
                    continue
                tf = frequency[term]
                norm = tf + self.k1 * (1 - self.b + self.b * length / (self.average_length or 1))
                score += self.idf.get(term, 0.0) * tf * (self.k1 + 1) / norm
            results.append(score)
        return results
