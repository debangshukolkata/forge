from __future__ import annotations

import threading

import pytest

from ratelimit import SlidingWindowLimiter, TokenBucket


class Clock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_bucket_starts_full_and_drains() -> None:
    clock = Clock()
    bucket = TokenBucket(rate=1, capacity=3, clock=clock)
    assert [bucket.try_acquire() for _ in range(4)] == [True, True, True, False]


def test_bucket_refills_continuously_and_caps_at_capacity() -> None:
    clock = Clock()
    bucket = TokenBucket(rate=2, capacity=4, clock=clock)
    assert bucket.try_acquire(4)
    clock.now += 0.5
    assert bucket.available() == pytest.approx(1.0)
    assert bucket.try_acquire() and not bucket.try_acquire()
    clock.now += 1000
    assert bucket.available() == pytest.approx(4.0)


def test_failed_acquire_takes_nothing() -> None:
    clock = Clock()
    bucket = TokenBucket(rate=1, capacity=5, clock=clock)
    assert bucket.try_acquire(3)
    assert not bucket.try_acquire(3)
    assert bucket.available() == pytest.approx(2.0)


def test_wait_time_is_exact_and_takes_nothing() -> None:
    clock = Clock()
    bucket = TokenBucket(rate=2, capacity=4, clock=clock)
    assert bucket.wait_time(4) == 0.0
    bucket.try_acquire(4)
    assert bucket.wait_time(1) == pytest.approx(0.5)
    assert bucket.wait_time(4) == pytest.approx(2.0)
    assert bucket.available() == pytest.approx(0.0)
    clock.now += 0.25
    assert bucket.wait_time(1) == pytest.approx(0.25)


def test_clock_going_backwards_adds_nothing_and_resets_the_reference() -> None:
    clock = Clock(100.0)
    bucket = TokenBucket(rate=1, capacity=10, clock=clock)
    bucket.try_acquire(10)
    clock.now = 50.0
    assert bucket.available() == pytest.approx(0.0)
    clock.now = 52.0  # two seconds after the new reference, not 52 after the old one
    assert bucket.available() == pytest.approx(2.0)


@pytest.mark.parametrize("rate,capacity", [(0, 1), (-1, 1), (1, 0), (1, 0.5)])
def test_bucket_rejects_bad_configuration(rate: float, capacity: float) -> None:
    with pytest.raises(ValueError):
        TokenBucket(rate, capacity)


@pytest.mark.parametrize("n", [0, -1, 6])
def test_bucket_rejects_impossible_requests(n: float) -> None:
    bucket = TokenBucket(1, 5, clock=Clock())
    with pytest.raises(ValueError):
        bucket.try_acquire(n)
    with pytest.raises(ValueError):
        bucket.wait_time(n)


def test_bucket_is_thread_safe() -> None:
    bucket = TokenBucket(rate=1, capacity=50, clock=Clock())
    results: list[bool] = []
    lock = threading.Lock()

    def worker() -> None:
        for _ in range(25):
            got = bucket.try_acquire()
            with lock:
                results.append(got)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 200 and sum(results) == 50


def test_window_allows_limit_events_then_blocks() -> None:
    clock = Clock()
    limiter = SlidingWindowLimiter(limit=3, window=10, clock=clock)
    assert [limiter.allow("a") for _ in range(4)] == [True, True, True, False]
    assert limiter.allow("b")  # keys are independent


def test_window_event_expires_exactly_at_t_plus_window() -> None:
    clock = Clock(0.0)
    limiter = SlidingWindowLimiter(limit=1, window=10, clock=clock)
    assert limiter.allow()
    clock.now = 9.999
    assert not limiter.allow()
    clock.now = 10.0
    assert limiter.allow()


def test_window_is_truly_sliding_not_fixed() -> None:
    clock = Clock(0.0)
    limiter = SlidingWindowLimiter(limit=2, window=10, clock=clock)
    assert limiter.allow()  # t=0
    clock.now = 6
    assert limiter.allow()  # t=6
    clock.now = 11  # the t=0 event expired, the t=6 one still counts
    assert limiter.allow()
    assert not limiter.allow()


def test_rejected_events_are_not_recorded() -> None:
    clock = Clock(0.0)
    limiter = SlidingWindowLimiter(limit=1, window=10, clock=clock)
    assert limiter.allow()
    clock.now = 5
    assert not limiter.allow()  # if this were recorded it would block until t=15
    clock.now = 10
    assert limiter.allow()


def test_retry_after_gives_the_time_until_a_slot_frees() -> None:
    clock = Clock(0.0)
    limiter = SlidingWindowLimiter(limit=2, window=10, clock=clock)
    assert limiter.retry_after() == 0.0
    limiter.allow()
    clock.now = 4
    limiter.allow()
    clock.now = 5
    assert limiter.retry_after() == pytest.approx(5.0)  # the t=0 event frees a slot at t=10
    assert limiter.retry_after() == pytest.approx(5.0)  # asking records nothing
    clock.now = 10
    assert limiter.retry_after() == 0.0


def test_retry_after_when_more_events_than_the_limit_are_counted() -> None:
    clock = Clock(0.0)
    limiter = SlidingWindowLimiter(limit=2, window=10, clock=clock)
    limiter.allow()
    clock.now = 1
    limiter.allow()
    clock.now = 2
    assert limiter.retry_after() == pytest.approx(8.0)


def test_expired_keys_are_forgotten() -> None:
    clock = Clock(0.0)
    limiter = SlidingWindowLimiter(limit=2, window=10, clock=clock)
    for i in range(100):
        limiter.allow(f"user{i}")
    assert limiter.tracked_keys() == 100
    clock.now = 10
    assert limiter.tracked_keys() == 0
    assert limiter.allow("user1")
    assert limiter.tracked_keys() == 1


@pytest.mark.parametrize("limit,window", [(0, 1), (-2, 1), (1, 0), (1, -5)])
def test_window_rejects_bad_configuration(limit: int, window: float) -> None:
    with pytest.raises(ValueError):
        SlidingWindowLimiter(limit, window)


def test_window_is_thread_safe() -> None:
    limiter = SlidingWindowLimiter(limit=40, window=1000, clock=Clock())
    results: list[bool] = []
    lock = threading.Lock()

    def worker() -> None:
        for _ in range(25):
            got = limiter.allow("k")
            with lock:
                results.append(got)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(results) == 40
