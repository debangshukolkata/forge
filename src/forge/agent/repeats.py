"""A memory of the tool calls of one loop, so an identical call with an identical answer can be told so (HW1).
A fact placed in the tool result, not a stuck detector: nothing is refused and no step is counted against
the model (D-155)."""

from __future__ import annotations

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

MAX_ENTRIES_PER_KEY = 20
MAX_KEYS = 2000


@dataclass(frozen=True)
class Entry:
    step: int
    tool_call_id: str
    digest: str
    ok: bool


def call_key(name: str, arguments: dict[str, Any] | None) -> str:
    return name + json.dumps(arguments or {}, sort_keys=True, default=str)


def digest_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


class RepeatLedger:
    def __init__(self) -> None:
        self._entries: OrderedDict[str, list[Entry]] = OrderedDict()

    def add(self, key: str, entry: Entry) -> None:
        entries = self._entries.setdefault(key, [])
        entries.append(entry)
        del entries[:-MAX_ENTRIES_PER_KEY]
        self._entries.move_to_end(key)
        while len(self._entries) > MAX_KEYS:
            self._entries.popitem(last=False)

    def seen(self, key: str, digest: str) -> Entry | None:
        """The latest earlier entry of this call with the same answer."""
        return next((e for e in reversed(self._entries.get(key, [])) if e.digest == digest), None)

    def first(self, key: str, digest: str) -> Entry | None:
        return next((e for e in self._entries.get(key, []) if e.digest == digest), None)

    def count(self, key: str, digest: str) -> int:
        """How many earlier entries of this call have the same answer."""
        return sum(1 for e in self._entries.get(key, []) if e.digest == digest)
