"""One PowerPoint job at a time, across processes (D-292). Preview and measure start PowerPoint through COM and quit it when they
are done if they started it; two DebCraft runs doing that at once (parallel benchmark runs, two projects) would have the first one
close PowerPoint under the second. A lock file in the temporary folder lets them take turns. A stale lock (its owner crashed) is
taken over after a while."""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

LOCK_NAME = "debcraft-powerpoint.lock"
STALE_AFTER_S = 300.0  # longer than any one preview or measure (their own timeout is 180 s)
POLL_S = 0.25
WAIT_LIMIT_S = 900.0


def _lock_path() -> Path:
    return Path(tempfile.gettempdir()) / LOCK_NAME


@contextmanager
def powerpoint_turn() -> Iterator[None]:
    path = _lock_path()
    deadline = time.monotonic() + WAIT_LIMIT_S
    while True:
        try:
            handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(handle, str(os.getpid()).encode())
            os.close(handle)
            break
        except FileExistsError:
            try:
                if time.time() - path.stat().st_mtime > STALE_AFTER_S:
                    path.unlink(missing_ok=True)
                    continue
            except OSError:
                continue  # it vanished between the two calls: try again
            if time.monotonic() > deadline:
                raise TimeoutError("PowerPoint stayed busy with another job for too long") from None
            time.sleep(POLL_S)
    try:
        yield
    finally:
        path.unlink(missing_ok=True)
