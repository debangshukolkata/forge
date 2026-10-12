import asyncio

import pytest

from jobs import JobResult, run_jobs


def test_results_keep_input_order_and_values() -> None:
    async def make(value: int, delay: float) -> int:
        await asyncio.sleep(delay)
        return value

    jobs = [lambda v=v, d=d: make(v, d) for v, d in [(1, 0.03), (2, 0.0), (3, 0.01)]]
    results = asyncio.run(run_jobs(jobs, concurrency=3))
    assert [(r.index, r.ok, r.value, r.attempts) for r in results] == [
        (0, True, 1, 1),
        (1, True, 2, 1),
        (2, True, 3, 1),
    ]
    assert all(isinstance(r, JobResult) for r in results)


def test_empty_list() -> None:
    assert asyncio.run(run_jobs([], concurrency=2)) == []


def test_concurrency_limit_is_respected_and_used() -> None:
    state = {"running": 0, "peak": 0}

    async def job() -> int:
        state["running"] += 1
        state["peak"] = max(state["peak"], state["running"])
        await asyncio.sleep(0.01)
        state["running"] -= 1
        return 1

    results = asyncio.run(run_jobs([job] * 12, concurrency=3))
    assert len(results) == 12 and all(r.ok for r in results)
    assert state["peak"] == 3


def test_retries_then_success_and_final_failure() -> None:
    calls = {"flaky": 0, "broken": 0}

    async def flaky() -> str:
        calls["flaky"] += 1
        if calls["flaky"] < 3:
            raise RuntimeError("not yet")
        return "done"

    async def broken() -> str:
        calls["broken"] += 1
        raise ValueError("always")

    results = asyncio.run(run_jobs([flaky, broken], concurrency=2, retries=2))
    assert (results[0].ok, results[0].value, results[0].attempts) == (True, "done", 3)
    assert results[1].ok is False and results[1].attempts == 3 and calls["broken"] == 3
    assert results[1].error and "always" in results[1].error


def test_zero_retries_means_one_attempt() -> None:
    calls = []

    async def broken() -> None:
        calls.append(1)
        raise RuntimeError("x")

    results = asyncio.run(run_jobs([broken], concurrency=1, retries=0))
    assert len(calls) == 1 and results[0].attempts == 1 and not results[0].ok


def test_one_failure_does_not_stop_the_others() -> None:
    async def good() -> int:
        return 5

    async def bad() -> int:
        raise RuntimeError("no")

    results = asyncio.run(run_jobs([bad, good, bad, good], concurrency=2, retries=0))
    assert [r.ok for r in results] == [False, True, False, True]


def test_retry_delay_grows_with_the_attempt_number() -> None:
    import time

    async def broken() -> None:
        raise RuntimeError("x")

    started = time.perf_counter()
    asyncio.run(run_jobs([broken], concurrency=1, retries=3, retry_delay=0.05))
    elapsed = time.perf_counter() - started
    assert 0.05 + 0.10 + 0.15 - 0.02 <= elapsed < 1.5  # waits 0.05, 0.10 and 0.15 seconds


def test_invalid_arguments() -> None:
    async def job() -> None:
        return None

    for kwargs in (
        {"concurrency": 0},
        {"concurrency": 1, "retries": -1},
        {"concurrency": 1, "retry_delay": -1},
    ):
        with pytest.raises(ValueError):
            asyncio.run(run_jobs([job], **kwargs))


def test_cancellation_propagates_and_stops_running_jobs() -> None:
    started: list[int] = []
    cancelled: list[int] = []

    async def slow(number: int) -> None:
        started.append(number)
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.append(number)
            raise

    async def scenario() -> None:
        task = asyncio.create_task(
            run_jobs([lambda n=n: slow(n) for n in range(3)], concurrency=3, retries=5)
        )
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(asyncio.wait_for(scenario(), timeout=5))
    assert sorted(started) == [0, 1, 2] and sorted(cancelled) == [0, 1, 2]
