"""One PowerPoint job at a time across processes (D-292)."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest

from forge.slides import powerpoint_lock
from forge.slides.powerpoint_lock import powerpoint_turn


@pytest.fixture(autouse=True)
def own_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(powerpoint_lock, "_lock_path", lambda: tmp_path / "pp.lock")
    monkeypatch.setattr(powerpoint_lock, "POLL_S", 0.01)


def test_jobs_take_turns() -> None:
    inside = 0
    worst = 0
    guard = threading.Lock()

    def job() -> None:
        nonlocal inside, worst
        with powerpoint_turn():
            with guard:
                inside += 1
                worst = max(worst, inside)
            time.sleep(0.02)
            with guard:
                inside -= 1

    threads = [threading.Thread(target=job) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert worst == 1


def test_the_lock_is_released_after_an_error(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError), powerpoint_turn():
        raise RuntimeError("boom")
    assert not (tmp_path / "pp.lock").exists()
    with powerpoint_turn():
        assert (tmp_path / "pp.lock").exists()


def test_a_stale_lock_is_taken_over(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock = tmp_path / "pp.lock"
    lock.write_text("999999")
    old = time.time() - 1000
    os.utime(lock, (old, old))
    with powerpoint_turn():
        assert lock.exists()
