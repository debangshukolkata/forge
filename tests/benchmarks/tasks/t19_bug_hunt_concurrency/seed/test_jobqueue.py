from __future__ import annotations

import pytest

from jobqueue import JobQueue, LeaseError


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_higher_priority_first() -> None:
    queue = JobQueue(Clock())
    queue.submit("a", priority=1)
    queue.submit("b", priority=5)
    assert [queue.claim("w").id, queue.claim("w").id] == ["b", "a"]  # type: ignore[union-attr]
    assert queue.claim("w") is None


def test_equal_priority_is_first_in_first_out() -> None:
    queue = JobQueue(Clock())
    for name in ["job10", "job9", "job2"]:
        queue.submit(name)
    assert [queue.claim("w").id for _ in range(3)] == ["job10", "job9", "job2"]  # type: ignore[union-attr]


def test_complete_and_unknown() -> None:
    queue = JobQueue(Clock())
    queue.submit("a")
    queue.claim("w1")
    queue.complete("a", "w1")
    assert queue.status("a") == "done"
    with pytest.raises(KeyError):
        queue.complete("zzz", "w1")
    with pytest.raises(ValueError):
        queue.submit("a")


def test_fail_by_a_stranger_is_refused() -> None:
    queue = JobQueue(Clock())
    queue.submit("a")
    queue.claim("w1")
    with pytest.raises(LeaseError):
        queue.fail("a", "w2")
