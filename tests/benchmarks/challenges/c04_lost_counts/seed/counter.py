"""A shared hit counter used by the web handlers."""

from __future__ import annotations

import time


class HitCounter:
    def __init__(self) -> None:
        self.value = 0
        self.last_hit_at = 0.0

    def increment(self) -> int:
        current = self.value
        self.last_hit_at = time.time()  # bookkeeping between the read and the write
        time.sleep(0)  # stands in for the logging call that used to be here: it lets another thread run
        self.value = current + 1
        return self.value

    def read(self) -> int:
        return self.value
