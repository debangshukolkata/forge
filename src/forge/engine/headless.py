"""Headless runs (spec §8, §13B): `forge run --workspace W --requirement-file F --auto-approve`.

--auto-approve is the free-hand cadence (D-130) for the whole run: Forge picks the recommended option at
design forks and approves ordinary commands — but never the always-ask list (A-9): those are refused and
the task is marked blocked. Requests for the user to do something are answered "can't" for the same reason.
Without --auto-approve, a question a headless run can't answer just gets Forge's best judgement (there is
no approval gate to refuse, per D-128 — Forge proceeds and states its assumptions).
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass

from forge.engine.events import Event, EventType
from forge.engine.inputs import Answer, Approve, Reject, SendMessage, UserInput
from forge.engine.session_host import SessionHost

HEADLESS_REFUSAL = (
    "Running headless: this action is on the always-ask list and nobody is here to approve it. "
    "Do not retry it; mark the task blocked with the reason, or find another way."
)
HEADLESS_CANT = "Running headless: nobody can do this right now."
PROCEED = (
    "Nobody is available to answer questions in this headless run. Use your best judgement, state your "
    "assumptions in REQUIREMENTS.md, and continue."
)
MAX_PROCEED_NUDGES = 2
EXIT_OK, EXIT_FAILED, EXIT_BLOCKED = 0, 1, 2


@dataclass
class HeadlessResult:
    exit_code: int
    activity: str
    tasks: list[dict[str, str]]
    errors: list[str]


def auto_reply(event: Event, auto_approve: bool) -> UserInput | None:
    payload = event.payload
    if event.type == EventType.APPROVAL_REQUESTED:
        if payload.get("always_ask") or not auto_approve:
            return Reject(request_id=payload["id"], instruction=HEADLESS_REFUSAL)
        return Approve(request_id=payload["id"])
    if event.type == EventType.QUESTION_ASKED:
        options = payload.get("options") or []
        choice = payload.get("recommended") or (options[0]["label"] if options else None)
        return Answer(question_id=payload["id"], choice=choice, text=None if choice else PROCEED)
    if event.type == EventType.USER_ACTION_REQUESTED:
        return Answer(question_id=payload["id"], choice="cant", text=HEADLESS_CANT)
    return None


async def run_headless(host: SessionHost, requirement: str | None, auto_approve: bool) -> HeadlessResult:
    assert host.orchestrator is not None
    errors: list[str] = []
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    if auto_approve:  # --auto-approve is the free-hand cadence (D-130) for the whole run
        host.orchestrator.set_cadence("free_hand")

    async def respond() -> None:
        async for event in subscription:
            if event.type == EventType.ERROR:
                errors.append(str(event.payload.get("message")))
            reply = auto_reply(event, auto_approve)
            if reply is not None:
                await host.submit(reply)

    responder = asyncio.create_task(respond())
    engine = asyncio.create_task(host.run())
    try:
        if requirement:
            await host.submit(SendMessage(text=requirement))
        for nudge in range(MAX_PROCEED_NUDGES + 1):
            await _wait_until_idle(host)
            if host.orchestrator.state.exported or errors or nudge == MAX_PROCEED_NUDGES:
                break
            await host.submit(SendMessage(text=PROCEED))  # the model asked something in plain text
        # state.exported flips as soon as the requirement is done; the retro (library card, lessons) now
        # runs after that point without blocking the user's turn (D-128), so a caller that wants to observe
        # its results — this one does, via the library/lessons assertions callers write against — waits for
        # it explicitly instead of racing the background task to close().
        await host.orchestrator.wait_idle()
    finally:
        subscription.close()
        await host.close()
        for task in (responder, engine):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    state = host.orchestrator.state
    tasks = [
        {"id": t.id, "title": t.title, "status": t.status, "note": t.verification or t.blocked_reason}
        for t in state.tasks
    ]
    blocked = any(t.status == "blocked" for t in state.tasks)
    code = EXIT_FAILED if errors else EXIT_OK if state.exported and not blocked else EXIT_BLOCKED
    return HeadlessResult(code, state.resume_summary(), tasks, errors)


async def _wait_until_idle(host: SessionHost) -> None:
    """Returns once no turn is running and nothing is queued."""
    await asyncio.sleep(0.2)
    while host.busy or not host.inputs_empty:
        await asyncio.sleep(0.2)
