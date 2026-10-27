"""A small in-memory job queue with leases, used by several worker threads.

Intended behaviour (the docstrings below repeat it):
- Jobs with a higher `priority` number are claimed first; jobs with the same priority are claimed in the order they were
  submitted (first in, first out).
- `claim(worker)` gives a job to exactly one worker and starts a lease of `lease_seconds`. Every claim is one attempt.
- Only the worker that currently holds a job's lease may `complete` or `fail` it. A job runs to completion exactly once.
- A job whose lease has run out is taken back by `reap_expired()`; finished jobs are never taken back.
- A job that fails (or whose lease expires) goes back to the queue, keeping its place among equal priorities, until it has
  used `max_attempts` attempts; then it is `dead` and is never claimed again.
"""

from __future__ import annotations

import heapq
import threading
import time
from dataclasses import dataclass, replace
from typing import Any, Callable


class LeaseError(Exception):
    """The worker does not hold the lease of that job."""


@dataclass
class Job:
    id: str
    payload: Any
    priority: int
    state: str = "queued"  # queued | running | done | dead
    worker: str | None = None
    attempts: int = 0
    seq: int = 0  # submission order: the tie-break among equal priorities


class JobQueue:
    def __init__(
        self, clock: Callable[[], float] = time.monotonic, lease_seconds: float = 30.0, max_attempts: int = 3
    ) -> None:
        if lease_seconds <= 0 or max_attempts < 1:
            raise ValueError("lease_seconds must be > 0 and max_attempts >= 1")
        self._clock = clock
        self._lease_seconds = lease_seconds
        self._max_attempts = max_attempts
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}
        self._heap: list[tuple[int, int, str]] = []
        self._leases: dict[str, float] = {}  # only jobs that are running right now
        self._next_seq = 0

    def submit(self, job_id: str, payload: Any = None, priority: int = 0) -> None:
        with self._lock:
            if job_id in self._jobs:
                raise ValueError(f"job {job_id} already exists")
            job = Job(job_id, payload, priority, seq=self._next_seq)
            self._next_seq += 1
            self._jobs[job_id] = job
            heapq.heappush(self._heap, (-priority, job.seq, job_id))

    def claim(self, worker: str) -> Job | None:
        """The next job for `worker`, or None when nothing is queued. Returns a copy of the job."""
        with self._lock:  # peek and pop in one critical section, or two workers could take the same job
            while self._heap:
                _, _, job_id = heapq.heappop(self._heap)
                job = self._jobs[job_id]
                if job.state != "queued":
                    continue
                job.state = "running"
                job.worker = worker
                job.attempts += 1
                self._leases[job_id] = self._clock() + self._lease_seconds
                return replace(job)
            return None

    def _held(self, job_id: str, worker: str) -> Job:
        job = self._jobs[job_id]  # KeyError for an unknown job
        if job.state != "running" or job.worker != worker:
            raise LeaseError(f"{worker} does not hold {job_id}")
        return job

    def complete(self, job_id: str, worker: str) -> None:
        with self._lock:
            job = self._held(job_id, worker)
            job.state = "done"
            job.worker = None
            self._leases.pop(job_id, None)

    def fail(self, job_id: str, worker: str) -> None:
        with self._lock:
            self._give_back(self._held(job_id, worker))

    def reap_expired(self) -> list[str]:
        """Take back jobs whose lease has run out; returns their ids in submission order."""
        now = self._clock()
        with self._lock:
            expired = sorted(
                (self._jobs[job_id] for job_id, expires in self._leases.items() if expires <= now),
                key=lambda job: job.seq,
            )
            for job in expired:
                self._give_back(job)
            return [job.id for job in expired]

    def status(self, job_id: str) -> str:
        with self._lock:
            return self._jobs[job_id].state

    def stats(self) -> dict[str, int]:
        with self._lock:
            counts = {"queued": 0, "running": 0, "done": 0, "dead": 0}
            for job in self._jobs.values():
                counts[job.state] += 1
            return counts

    def _give_back(self, job: Job) -> None:
        job.worker = None
        self._leases.pop(job.id, None)
        if job.attempts >= self._max_attempts:
            job.state = "dead"
        else:
            job.state = "queued"
            heapq.heappush(self._heap, (-job.priority, job.seq, job.id))
