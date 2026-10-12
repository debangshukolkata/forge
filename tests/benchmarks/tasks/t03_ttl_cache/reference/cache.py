import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any


class TTLCache:
    def __init__(self, capacity: int, ttl: float, clock: Callable[[], float] = time.monotonic) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        self.capacity = capacity
        self.ttl = ttl
        self._clock = clock
        self._items: OrderedDict[Any, tuple[Any, float]] = OrderedDict()

    def _expired(self, stored_at: float) -> bool:
        return self._clock() - stored_at >= self.ttl

    def _purge(self) -> None:
        for key in [k for k, (_, stored_at) in self._items.items() if self._expired(stored_at)]:
            del self._items[key]

    def set(self, key: Any, value: Any) -> None:
        self._items[key] = (value, self._clock())
        self._items.move_to_end(key)
        if len(self._items) > self.capacity:
            self._purge()
        while len(self._items) > self.capacity:
            self._items.popitem(last=False)

    def get(self, key: Any, default: Any = None) -> Any:
        entry = self._items.get(key)
        if entry is None:
            return default
        if self._expired(entry[1]):
            del self._items[key]
            return default
        self._items.move_to_end(key)
        return entry[0]

    def delete(self, key: Any) -> bool:
        entry = self._items.pop(key, None)
        return entry is not None and not self._expired(entry[1])

    def __len__(self) -> int:
        self._purge()
        return len(self._items)

    def __contains__(self, key: Any) -> bool:
        entry = self._items.get(key)
        return entry is not None and not self._expired(entry[1])
