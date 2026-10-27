from __future__ import annotations

import sys
import threading

import pytest

from jobqueue import JobQueue, LeaseError


class Clock:
    def __init__(self) -> None:
        self.now = 100.0

    def __call__(self) -> float:
        return self.now


def make(**kwargs: object) -> tuple[JobQueue, Clock]:
    clock = Clock()
    return JobQueue(clock, **kwargs), clock  # type: ignore[arg-type]


def drain(queue: JobQueue, worker: str = "w") -> list[str]:
    out = []
    while (job := queue.claim(worker)) is not None:
        out.append(job.id)
    return out


def test_fifo_among_equal_priorities_whatever_the_ids_look_like() -> None:
    queue, _ = make()
    for name in ["job10", "job9", "job2", "b", "a", "job1"]:
        queue.submit(name)
    assert drain(queue) == ["job10", "job9", "job2", "b", "a", "job1"]


def test_priority_beats_age_and_ties_stay_fifo() -> None:
    queue, _ = make()
    queue.submit("low1", priority=0)
    queue.submit("hi-b", priority=5)
    queue.submit("mid", priority=2)
    queue.submit("hi-a", priority=5)
    queue.submit("low0", priority=-3)
    assert drain(queue) == ["hi-b", "hi-a", "mid", "low1", "low0"]


def test_failed_job_keeps_its_place_among_equal_priorities() -> None:
    queue, _ = make()
    for name in ["z1", "a2", "m3"]:
        queue.submit(name)
    first = queue.claim("w")
    assert first.id == "z1"  # type: ignore[union-attr]
    queue.fail("z1", "w")
    assert drain(queue) == ["z1", "a2", "m3"]


def test_reaped_job_keeps_its_place_and_counts_an_attempt() -> None:
    queue, clock = make(lease_seconds=10)
    queue.submit("late-name-z")
    queue.submit("early-name-a")
    queue.claim("w1")
    clock.now += 10
    assert queue.reap_expired() == ["late-name-z"]
    again = queue.claim("w2")
    assert (again.id, again.attempts, again.worker) == ("late-name-z", 2, "w2")  # type: ignore[union-attr]
    assert queue.claim("w2").id == "early-name-a"  # type: ignore[union-attr]


def test_stale_worker_cannot_complete_a_reassigned_job() -> None:
    queue, clock = make(lease_seconds=10)
    queue.submit("a")
    queue.claim("slow")
    clock.now += 11
    assert queue.reap_expired() == ["a"]
    assert queue.claim("fast").id == "a"  # type: ignore[union-attr]
    with pytest.raises(LeaseError):
        queue.complete("a", "slow")
    with pytest.raises(LeaseError):
        queue.fail("a", "slow")
    assert queue.status("a") == "running"
    queue.complete("a", "fast")
    assert queue.status("a") == "done"
    assert queue.stats() == {"queued": 0, "running": 0, "done": 1, "dead": 0}


def test_a_job_completes_exactly_once() -> None:
    queue, _ = make()
    queue.submit("a")
    queue.claim("w")
    queue.complete("a", "w")
    with pytest.raises(LeaseError):
        queue.complete("a", "w")
    with pytest.raises(LeaseError):
        queue.fail("a", "w")
    assert queue.stats()["done"] == 1


def test_complete_by_a_stranger_or_on_a_queued_job_is_refused() -> None:
    queue, _ = make()
    queue.submit("a")
    with pytest.raises(LeaseError):
        queue.complete("a", "w")  # nobody claimed it
    queue.claim("w1")
    with pytest.raises(LeaseError):
        queue.complete("a", "w2")
    assert queue.status("a") == "running"
    with pytest.raises(KeyError):
        queue.complete("nope", "w1")
    with pytest.raises(KeyError):
        queue.fail("nope", "w1")
    with pytest.raises(KeyError):
        queue.status("nope")


def test_finished_jobs_are_never_reaped_or_handed_out_again() -> None:
    queue, clock = make(lease_seconds=5)
    queue.submit("a")
    queue.submit("b")
    queue.claim("w")
    queue.complete("a", "w")
    clock.now += 1000
    assert queue.reap_expired() == []
    assert queue.status("a") == "done"
    assert drain(queue) == ["b"]  # a is not back
    clock.now += 1000
    assert queue.reap_expired() == ["b"]
    assert queue.reap_expired() == []  # already taken back


def test_failed_job_is_not_reaped_later_as_well() -> None:
    queue, clock = make(lease_seconds=5)
    queue.submit("a")
    queue.claim("w")
    queue.fail("a", "w")
    clock.now += 100
    assert queue.reap_expired() == []
    assert queue.stats()["queued"] == 1
    assert drain(queue) == ["a"]


def test_lease_boundary_is_inclusive_and_reap_order_is_submission_order() -> None:
    queue, clock = make(lease_seconds=10)
    for name in ["y", "x", "w"]:
        queue.submit(name)
    for _ in range(3):
        queue.claim("w1")
    clock.now = 109.5
    assert queue.reap_expired() == []
    clock.now = 110.0
    assert queue.reap_expired() == ["y", "x", "w"]


def test_each_claim_restarts_the_lease() -> None:
    queue, clock = make(lease_seconds=10)
    queue.submit("a")
    queue.claim("w1")
    clock.now += 10
    queue.reap_expired()
    queue.claim("w2")
    clock.now += 9
    assert queue.reap_expired() == []
    clock.now += 1
    assert queue.reap_expired() == ["a"]


@pytest.mark.parametrize("via", ["fail", "reap"])
def test_a_job_gets_exactly_max_attempts(via: str) -> None:
    queue, clock = make(max_attempts=3, lease_seconds=1)
    queue.submit("a")
    attempts = 0
    while (job := queue.claim("w")) is not None:
        attempts += 1
        assert job.attempts == attempts
        if via == "fail":
            queue.fail("a", "w")
        else:
            clock.now += 1
            queue.reap_expired()
        assert attempts <= 3
    assert attempts == 3
    assert queue.status("a") == "dead"
    assert queue.stats() == {"queued": 0, "running": 0, "done": 0, "dead": 1}


def test_max_attempts_one_means_no_retry() -> None:
    queue, _ = make(max_attempts=1)
    queue.submit("a")
    queue.claim("w")
    queue.fail("a", "w")
    assert queue.status("a") == "dead" and queue.claim("w") is None


def test_dead_job_is_not_handed_out_and_does_not_block_others() -> None:
    queue, _ = make(max_attempts=1)
    queue.submit("a", priority=9)
    queue.submit("b")
    queue.claim("w")
    queue.fail("a", "w")
    assert drain(queue) == ["b"]


def test_claim_returns_a_copy() -> None:
    queue, _ = make()
    queue.submit("a", payload={"n": 1})
    job = queue.claim("w")
    job.state = "done"  # type: ignore[union-attr]
    job.worker = "someone else"  # type: ignore[union-attr]
    assert queue.status("a") == "running"
    queue.complete("a", "w")  # still held by w


def test_submit_rules_and_constructor_validation() -> None:
    queue, _ = make()
    queue.submit("a", payload=[1, 2], priority=3)
    with pytest.raises(ValueError):
        queue.submit("a")
    queue.claim("w")
    queue.complete("a", "w")
    with pytest.raises(ValueError):
        queue.submit("a")  # finished ids are not reusable either
    for kwargs in ({"lease_seconds": 0}, {"lease_seconds": -1.0}, {"max_attempts": 0}):
        with pytest.raises(ValueError):
            JobQueue(Clock(), **kwargs)  # type: ignore[arg-type]
    job = JobQueue(Clock())
    job.submit("p", payload={"k": "v"}, priority=2)
    claimed = job.claim("w")
    assert (claimed.payload, claimed.priority, claimed.state, claimed.worker, claimed.attempts) == (  # type: ignore[union-attr]
        {"k": "v"},
        2,
        "running",
        "w",
        1,
    )


def test_empty_queue_and_stats() -> None:
    queue, _ = make()
    assert queue.claim("w") is None
    assert queue.reap_expired() == []
    assert queue.stats() == {"queued": 0, "running": 0, "done": 0, "dead": 0}
    queue.submit("a")
    queue.submit("b")
    queue.submit("c")
    queue.claim("w")
    assert queue.stats() == {"queued": 2, "running": 1, "done": 0, "dead": 0}


def test_many_threads_claim_every_job_exactly_once() -> None:
    queue = JobQueue()
    total = 600
    for number in range(total):
        queue.submit(f"j{number}", priority=number % 3)
    claimed: list[list[str]] = [[] for _ in range(8)]
    barrier = threading.Barrier(8)
    errors: list[BaseException] = []

    def work(index: int) -> None:
        try:
            barrier.wait()
            while (job := queue.claim(f"w{index}")) is not None:
                claimed[index].append(job.id)
                queue.complete(job.id, f"w{index}")
        except BaseException as error:  # noqa: BLE001 - reported below
            errors.append(error)

    previous = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        threads = [threading.Thread(target=work, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)
    finally:
        sys.setswitchinterval(previous)
    assert not errors, errors
    everything = [job_id for part in claimed for job_id in part]
    assert len(everything) == total and len(set(everything)) == total
    assert queue.stats() == {"queued": 0, "running": 0, "done": total, "dead": 0}
    for part in claimed:  # inside one priority level a worker sees the jobs in submission order
        for level in (0, 1, 2):
            numbers = [int(job_id[1:]) for job_id in part if int(job_id[1:]) % 3 == level]
            assert numbers == sorted(numbers)
