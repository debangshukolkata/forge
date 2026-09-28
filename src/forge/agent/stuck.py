"""Stuck detection (spec §13.3). The detector watches every tool call of the current task:

- the same call with the same arguments 3+ times with no edit in between (re-running tests after a fix is
  progress; re-running them without changing anything is not);
- the same error signature 3+ times (the fix isn't working);
- edit/revert oscillation: a file returns to a content it had before, twice;
- no progress (no new file content, no new passing test, no new error) for K steps;
- more than max_fix_attempts failed verifications in the task (spec §13.2).

Each trigger raises the escalation level by one; the agent loop acts on it (agent/escalation.py). After a
trigger the counters that caused it restart, so one problem escalates one level at a time.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field

REPEAT_LIMIT = 3
NO_PROGRESS_STEPS = 25
FILE_TOOLS = {"write_file", "edit_file", "multi_edit"}
VERIFY_TOOLS = {"run_tests", "verify", "python_run", "run_command"}


@dataclass
class StuckSignal:
    reason: str  # human-readable, also shown to the model
    kind: str  # repeat_call | repeat_error | oscillation | no_progress | fix_attempts


@dataclass
class StuckDetector:
    max_fix_attempts: int = 5
    no_progress_steps: int = NO_PROGRESS_STEPS
    calls: Counter[str] = field(default_factory=Counter)
    errors: Counter[str] = field(default_factory=Counter)
    failed_verifications: int = 0
    file_history: dict[str, list[str]] = field(default_factory=dict)
    reverts: Counter[str] = field(default_factory=Counter)
    steps: int = 0
    last_progress_step: int = 0
    edits: int = 0
    seen_errors: set[str] = field(default_factory=set)
    failed_approaches: list[str] = field(default_factory=list)

    def reset(self) -> None:
        """A new task: everything starts over."""
        fresh = StuckDetector(self.max_fix_attempts, self.no_progress_steps)
        self.__dict__.update(fresh.__dict__)

    def observe(
        self,
        tool: str,
        arguments: dict[str, object],
        ok: bool,
        error_signature: str | None = None,
        file_path: str | None = None,
        file_content_hash: str | None = None,
        tests_passed: bool = False,
    ) -> StuckSignal | None:
        self.steps += 1
        signals: list[StuckSignal] = []
        call_key = f"{self.edits}|{tool}|{json.dumps(arguments, sort_keys=True, default=str)}"
        self.calls[call_key] += 1
        if self.calls[call_key] >= REPEAT_LIMIT:
            signals.append(
                StuckSignal(
                    f"the same {tool} call ran {self.calls[call_key]} times with no change in between",
                    "repeat_call",
                )
            )
            self.calls[call_key] = 0

        if file_path and file_content_hash and tool in FILE_TOOLS and ok:
            history = self.file_history.setdefault(file_path, [])
            if file_content_hash in history[:-1]:  # back to an earlier version (not just unchanged)
                self.reverts[file_path] += 1
                if self.reverts[file_path] >= 2:
                    signals.append(
                        StuckSignal(
                            f"{file_path} keeps going back to earlier versions (edit/revert oscillation)",
                            "oscillation",
                        )
                    )
                    self.reverts[file_path] = 0
            elif not history or history[-1] != file_content_hash:
                self._progress()
            history.append(file_content_hash)
            self.edits += 1

        if tests_passed:
            self._progress()
        if not ok and error_signature:
            if error_signature not in self.seen_errors:
                self.seen_errors.add(error_signature)
                self._progress()  # a new error is movement too
            self.errors[error_signature] += 1
            if tool in VERIFY_TOOLS:
                self.failed_verifications += 1
                self.failed_approaches.append(f"step {self.steps}: {error_signature[:160]}")
            if self.errors[error_signature] >= REPEAT_LIMIT:
                signals.append(
                    StuckSignal(
                        f"the same error came back {self.errors[error_signature]} times: "
                        f"{error_signature[:200]}",
                        "repeat_error",
                    )
                )
                self.errors[error_signature] = 0
        if self.failed_verifications > self.max_fix_attempts:
            signals.append(
                StuckSignal(
                    f"{self.failed_verifications} failed verification runs in this task "
                    f"(limit {self.max_fix_attempts})",
                    "fix_attempts",
                )
            )
            self.failed_verifications = 0
        if self.steps - self.last_progress_step >= self.no_progress_steps:
            signals.append(
                StuckSignal(f"no progress in the last {self.no_progress_steps} steps", "no_progress")
            )
            self.last_progress_step = self.steps
        return signals[0] if signals else None

    def _progress(self) -> None:
        self.last_progress_step = self.steps


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]
