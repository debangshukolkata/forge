"""Token bucket and sliding window rate limiters with an injectable clock."""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable


class TokenBucket:
    def __init__(self, rate: float, capacity: float, clock: Callable[[], float] = time.monotonic) -> None:
        if rate <= 0:
            raise ValueError("rate must be greater than 0")
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.rate = float(rate)
        self.capacity = float(capacity)
        self._clock = clock
        self._tokens = float(capacity)
        self._last = clock()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = self._clock()
        elapsed = now - self._last
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last = now

    def _check(self, n: float) -> None:
        if n <= 0 or n > self.capacity:
            raise ValueError(f"n must be greater than 0 and at most {self.capacity}")

    def try_acquire(self, n: float = 1) -> bool:
        self._check(n)
        with self._lock:
            self._refill()
            if self._tokens >= n:
                self._tokens -= n
                return True
            return False

    def wait_time(self, n: float = 1) -> float:
        self._check(n)
        with self._lock:
            self._refill()
            missing = n - self._tokens
            return 0.0 if missing <= 0 else missing / self.rate

    def available(self) -> float:
        with self._lock:
            self._refill()
            return self._tokens


class SlidingWindowLimiter:
    def __init__(self, limit: int, window: float, clock: Callable[[], float] = time.monotonic) -> None:
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if window <= 0:
            raise ValueError("window must be greater than 0")
        self.limit = limit
        self.window = float(window)
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _expire(self, key: str, now: float) -> deque[float] | None:
        events = self._events.get(key)
        if events is None:
            return None
        while events and events[0] + self.window <= now:
            events.popleft()
        if not events:
            del self._events[key]
            return None
        return events

    def allow(self, key: str = "") -> bool:
        with self._lock:
            now = self._clock()
            events = self._expire(key, now)
            if events is not None and len(events) >= self.limit:
                return False
            self._events.setdefault(key, deque()).append(now)
            return True

    def retry_after(self, key: str = "") -> float:
        with self._lock:
            now = self._clock()
            events = self._expire(key, now)
            if events is None or len(events) < self.limit:
                return 0.0
            # the event whose expiry frees a slot is the one `limit` places from the newest
            return events[len(events) - self.limit] + self.window - now

    def tracked_keys(self) -> int:
        with self._lock:
            now = self._clock()
            for key in list(self._events):
                self._expire(key, now)
            return len(self._events)
