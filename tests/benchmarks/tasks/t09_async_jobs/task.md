Create a Python module `jobs.py` that runs many async jobs with limited concurrency and retries.

```python
@dataclass
class JobResult:
    index: int            # position of the job in the input list
    ok: bool
    value: Any = None     # the job's return value when ok
    error: str | None = None   # repr-style text of the last exception when not ok
    attempts: int = 0     # how many times the job was started

async def run_jobs(jobs, concurrency: int, retries: int = 2, retry_delay: float = 0.0) -> list[JobResult]
```

- `jobs` is a list of zero-argument callables, each returning an awaitable (call it to start a fresh attempt).
- At most `concurrency` jobs run at the same time. `concurrency < 1` raises `ValueError`; so does `retries < 0` or `retry_delay < 0`.
- A job that raises an `Exception` is tried again, up to `retries` extra times (so at most `retries + 1` attempts), waiting `retry_delay * attempt_number` seconds before each retry (the first retry waits `retry_delay`, the second `2 * retry_delay`, ...). After the last failure the result has `ok=False` and `error` set; the other jobs carry on.
- The results are returned in the order of `jobs`, whatever order the jobs finish in. An empty list gives an empty list.
- Cancelling `run_jobs` (task cancellation) must cancel the running jobs and propagate `asyncio.CancelledError`; it must not be swallowed by the retry logic.

Write tests for it too (use `asyncio.run`, no extra packages). Use only the standard library.
