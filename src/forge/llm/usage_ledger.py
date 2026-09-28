"""Tokens and cost per phase and per task of a project (DECISIONS D-118), kept in .forge/usage.json so the
numbers survive restarts and add up across sessions. Every model call is filed under the phase and task that
were active when it was made (subagents — reviewer, debugger, summaries — count where they ran)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from forge.llm.base import Usage

EMPTY = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 0}


class UsageLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {"total": dict(EMPTY), "by_phase": {}, "by_task": {}}
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self._data.update({k: loaded[k] for k in ("total", "by_phase", "by_task") if k in loaded})
        except (OSError, ValueError):
            pass  # a new project, or an unreadable file: start counting again

    def add(self, phase: str, task: str | None, usage: Usage, cost_usd: float) -> None:
        with self._lock:
            buckets = [self._data["total"], self._data["by_phase"].setdefault(phase, dict(EMPTY))]
            if task:
                buckets.append(self._data["by_task"].setdefault(task, dict(EMPTY)))
            for bucket in buckets:
                bucket["input_tokens"] += usage.input_tokens
                bucket["output_tokens"] += usage.output_tokens
                bucket["cost_usd"] = round(bucket["cost_usd"] + cost_usd, 6)
                bucket["calls"] += 1
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data, indent=1), encoding="utf-8")

    def summary(self) -> dict[str, Any]:
        with self._lock:
            copy: dict[str, Any] = json.loads(json.dumps(self._data))  # a snapshot, not the live dict
            return copy
