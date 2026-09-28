"""Retry with exponential backoff that honours the server's Retry-After (spec §5.3)."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from forge.config import RetryConfig
from forge.errors import LLMError, LLMRateLimitError

T = TypeVar("T")
Sleeper = Callable[[float], Awaitable[None]]
RetryCallback = Callable[[int, LLMError, float], Awaitable[None]]

# Never wait longer than this for one retry, whatever the server asks for.
MAX_HONOURED_RETRY_AFTER_S = 300.0


def compute_delay(attempt: int, error: LLMError, config: RetryConfig, jitter: float | None = None) -> float:
    if isinstance(error, LLMRateLimitError) and error.retry_after_s is not None:
        return min(max(error.retry_after_s, 0.0), MAX_HONOURED_RETRY_AFTER_S)
    backoff = config.base_delay_s * (2.0 ** (attempt - 1))
    # Jitter (50-100% of the backoff) avoids retry storms when several calls fail together.
    factor = 0.5 + 0.5 * (random.random() if jitter is None else jitter)
    return min(backoff * factor, config.max_delay_s)


async def with_retries(
    operation: Callable[[], Awaitable[T]],
    config: RetryConfig,
    sleep: Sleeper = asyncio.sleep,
    on_retry: RetryCallback | None = None,
) -> T:
    attempt = 1
    while True:
        try:
            return await operation()
        except LLMError as error:
            if not error.retryable or attempt >= config.max_attempts:
                raise
            delay = compute_delay(attempt, error, config)
            if on_retry is not None:
                await on_retry(attempt, error, delay)
            await sleep(delay)
            attempt += 1
