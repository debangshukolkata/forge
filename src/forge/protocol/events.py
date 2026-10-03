"""UI-agnostic event bus (spec §15A.2).

The engine publishes typed events; the terminal and web UIs subscribe. Every event gets a sequence
number and is appended to a JSONL log, so a UI that reconnects asks for "events since N" and loses
nothing. Payloads are redacted before they are stored or delivered.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from forge.safety.redact import Redactor, default_redactor


class EventType(StrEnum):
    USER_MESSAGE = "user_message"  # what the user sent, so a UI replay shows both sides
    MESSAGE_DELTA = "message_delta"
    THINKING_DELTA = (
        "thinking_delta"  # a finished piece of the model's reasoning summary (progress while it thinks)
    )
    MESSAGE_DONE = "message_done"
    LLM_CALL = "llm_call"  # one model call: latency, tokens, tool calls asked for (run log; no UI row)
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_FINISHED = "tool_call_finished"
    APPROVAL_REQUESTED = "approval_requested"
    QUESTION_ASKED = "question_asked"
    USER_ACTION_REQUESTED = "user_action_requested"
    DB_REQUEST_CREATED = "db_request_created"
    DB_REQUEST_UPDATED = "db_request_updated"
    TASK_LIST_UPDATED = "task_list_updated"
    TODO_UPDATED = "todo_updated"  # the model's own todo list, whole list each time (D-177)
    FILE_CHANGED = "file_changed"
    CONTEXT_UPDATED = "context_updated"
    COST_UPDATED = "cost_updated"
    STATUS_CHANGED = "status_changed"
    EVAL_REPORT_READY = "eval_report_ready"
    LESSON_PROPOSED = "lesson_proposed"
    IMPROVEMENT_PROPOSED = "improvement_proposed"
    AGENT_STARTED = (
        "agent_started"  # a subagent (reviewer, debugger, helper, analysis) began (Run map, D-119)
    )
    AGENT_FINISHED = "agent_finished"
    NOTICE = "notice"  # informational: retries, fallbacks, queued input, slash-command output
    ERROR = "error"


class Event(BaseModel):
    seq: int
    type: EventType
    ts: str
    payload: dict[str, Any]
    # The phase and task active when the event happened (the Run map groups events by them); None when the
    # session doesn't follow phases.
    where: dict[str, str | None] | None = None


class EventBus:
    def __init__(self, log_path: Path | None = None, redactor: Redactor = default_redactor) -> None:
        self._log_path = log_path
        self._redactor = redactor
        self._events: list[Event] = []
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self.stamp: Callable[[], dict[str, str | None]] | None = None  # set by the session (phase/task)
        if log_path is not None:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            if log_path.exists():
                self._events = load_event_log(log_path)

    @property
    def last_seq(self) -> int:
        return self._events[-1].seq if self._events else 0

    async def publish(self, event_type: EventType, payload: dict[str, Any] | None = None) -> Event:
        event = Event(
            seq=self.last_seq + 1,
            type=event_type,
            ts=datetime.now(UTC).isoformat(timespec="milliseconds"),
            payload=self._redactor.redact_data(payload or {}),
            where=self.stamp() if self.stamp is not None else None,
        )
        self._events.append(event)
        if self._log_path is not None:
            with self._log_path.open("a", encoding="utf-8") as log:
                log.write(event.model_dump_json() + "\n")
        for queue in list(self._subscribers):
            queue.put_nowait(event)
        return event

    def events_since(self, seq: int) -> list[Event]:
        return [event for event in self._events if event.seq > seq]

    def subscribe(self, since_seq: int = 0) -> Subscription:
        return Subscription(self, since_seq)

    def _add_queue(self, queue: asyncio.Queue[Event]) -> None:
        self._subscribers.add(queue)

    def _remove_queue(self, queue: asyncio.Queue[Event]) -> None:
        self._subscribers.discard(queue)


class Subscription:
    """Async iterator: first replays events after since_seq, then yields live events in order."""

    def __init__(self, bus: EventBus, since_seq: int) -> None:
        self._bus = bus
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        # Register before taking the replay snapshot so no event can fall between the two.
        bus._add_queue(self._queue)
        self._backlog = bus.events_since(since_seq)
        self._last_seq = since_seq

    def __aiter__(self) -> Subscription:
        return self

    async def __anext__(self) -> Event:
        while True:
            event = self._backlog.pop(0) if self._backlog else await self._queue.get()
            if event.seq > self._last_seq:
                self._last_seq = event.seq
                return event

    def close(self) -> None:
        self._bus._remove_queue(self._queue)


def load_event_log(path: Path) -> list[Event]:
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(Event.model_validate(json.loads(line)))
    return events
