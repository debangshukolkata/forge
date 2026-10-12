from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class JobResult:
    index: int
    ok: bool
    value: Any = None
    error: str | None = None
    attempts: int = 0


async def run_jobs(
    jobs: list[Callable[[], Awaitable[Any]]], concurrency: int, retries: int = 2, retry_delay: float = 0.0
) -> list[JobResult]:
    if concurrency < 1 or retries < 0 or retry_delay < 0:
        raise ValueError("concurrency must be at least 1; retries and retry_delay cannot be negative")
    semaphore = asyncio.Semaphore(concurrency)

    async def run_one(index: int, job: Callable[[], Awaitable[Any]]) -> JobResult:
        async with semaphore:
            result = JobResult(index=index, ok=False)
            for attempt in range(1, retries + 2):
                result.attempts = attempt
                try:
                    result.value = await job()
                except Exception as error:
                    result.error = repr(error)
                    if attempt <= retries:
                        await asyncio.sleep(retry_delay * attempt)
                else:
                    result.ok = True
                    result.error = None
                    return result
            return result

    return list(await asyncio.gather(*(run_one(i, job) for i, job in enumerate(jobs))))
