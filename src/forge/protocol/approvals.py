"""Approval requests: the engine asks, a UI answers (Approve/Reject inputs), the waiting call resumes."""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass
from typing import Any, Literal

from forge.protocol.events import EventBus, EventType
from forge.protocol.inputs import Answer, Approve, Reject


@dataclass
class ApprovalAnswer:
    approved: bool
    scope: Literal["once", "prefix"] = "once"
    instruction: str | None = None


class ApprovalBroker:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._pending: dict[str, asyncio.Future[ApprovalAnswer]] = {}
        self._ids = itertools.count(1)

    @property
    def pending_ids(self) -> list[str]:
        return list(self._pending)

    async def request(self, payload: dict[str, Any]) -> ApprovalAnswer:
        request_id = f"approval-{next(self._ids)}"
        future: asyncio.Future[ApprovalAnswer] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        await self._bus.publish(EventType.APPROVAL_REQUESTED, {"id": request_id, **payload})
        try:
            return await future
        finally:
            self._pending.pop(request_id, None)

    def reject_all(self, instruction: str) -> int:
        """A chat message while cards are open means 'no, do this instead' (D-153): the waiting calls resume
        declined, carrying the message as the instruction, so the turn can end and the message can run."""
        count = 0
        for future in self._pending.values():
            if not future.done():
                future.set_result(ApprovalAnswer(approved=False, instruction=instruction))
                count += 1
        return count

    def resolve(self, answer: Approve | Reject) -> bool:
        future = self._pending.get(answer.request_id)
        if future is None or future.done():
            return False
        if isinstance(answer, Approve):
            future.set_result(ApprovalAnswer(approved=True, scope=answer.scope))
        else:
            future.set_result(ApprovalAnswer(approved=False, instruction=answer.instruction))
        return True


@dataclass
class QuestionAnswer:
    choice: str | None = None  # the option label picked (or "done"/"skip"/"cant" for user actions)
    text: str | None = None  # free text: "Other…", an instruction, or pasted output


class QuestionBroker:
    """Design-fork questions and user-action requests (spec §7, §9.4), answered with Answer inputs."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._pending: dict[str, asyncio.Future[QuestionAnswer]] = {}
        self._ids = itertools.count(1)

    @property
    def pending_ids(self) -> list[str]:
        return list(self._pending)

    async def ask(self, event_type: EventType, payload: dict[str, Any]) -> QuestionAnswer:
        question_id = f"question-{next(self._ids)}"
        future: asyncio.Future[QuestionAnswer] = asyncio.get_running_loop().create_future()
        self._pending[question_id] = future
        await self._bus.publish(event_type, {"id": question_id, **payload})
        try:
            return await future
        finally:
            self._pending.pop(question_id, None)

    def answer_all_with_text(self, text: str) -> int:
        """Like ApprovalBroker.reject_all: a typed message answers every open question as free text."""
        count = 0
        for future in self._pending.values():
            if not future.done():
                future.set_result(QuestionAnswer(text=text))
                count += 1
        return count

    def resolve(self, answer: Answer) -> bool:
        future = self._pending.get(answer.question_id)
        if future is None or future.done():
            return False
        future.set_result(QuestionAnswer(choice=answer.choice, text=answer.text))
        return True
