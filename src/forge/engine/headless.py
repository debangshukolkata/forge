"""Headless runs (spec §8, §13B): `forge run --workspace W --requirement-file F --auto-approve`.

--auto-approve is the free-hand cadence (D-130) for the whole run: DebCraft picks the recommended option at
design forks and approves ordinary commands — but never the always-ask list (A-9): those are refused and
the task is marked blocked. Requests for the user to do something are answered "can't" for the same reason.
Without --auto-approve, a question a headless run can't answer just gets DebCraft's best judgement (there is
no approval gate to refuse, per D-128 — DebCraft proceeds and states its assumptions).
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from forge.engine.session_host import SessionHost
from forge.engine.timebox import TimeBox
from forge.protocol.events import Event, EventType
from forge.protocol.inputs import Answer, Approve, Interrupt, Reject, SendMessage, UserInput

HEADLESS_REFUSAL = (
    "Running headless: this action is on the always-ask list and nobody is here to approve it. "
    "Do not retry it; mark the task blocked with the reason, or find another way."
)
HEADLESS_CANT = "Running headless: nobody can do this right now."
PROCEED = (
    "Nobody is available to answer questions in this headless run. Use your best judgement, state your "
    "assumptions in REQUIREMENTS.md, and continue."
)
MAX_PROCEED_NUDGES = 2  # in a row without progress: a model that does nothing after two nudges is stuck
MAX_TOTAL_NUDGES = 40  # runaway guard over the whole run
# A long build ends many turns while tasks are still open; the first version allowed two nudges per RUN, so the BO6 support-desk
# run (2026-10-29) stopped after 30 minutes with 4 of 7 tasks open although the model's last words were "I'll continue now" (D-538).
EXIT_OK, EXIT_FAILED, EXIT_BLOCKED = 0, 1, 2
EXIT_TIMEBOX = 3  # the time box ended the run (wrapped up, or stopped at the hard limit) and the work is not finished (D-460)


@dataclass
class HeadlessResult:
    exit_code: int
    activity: str
    tasks: list[dict[str, str]]
    errors: list[str]
    installs: list[str] = field(
        default_factory=list
    )  # package installs approved by --allow-installs, in order


PIP_INSTALL = re.compile(r"^\s*(?:\S*python[\w.]*(?:\.exe)?\s+-m\s+pip|pip[\w.]*)\s+install\b", re.IGNORECASE)
# Anything that sends the install somewhere else, installs from an address or leaves the project environment is never approved.
INSTALL_REFUSED = re.compile(
    r"://|git\+|--target|--user|--prefix|--root|--index-url|-i\s|--extra-index-url|--trusted-host|--find-links|-f\s|--no-verify|&&|;|\||`|\$\(",
    re.IGNORECASE,
)


def is_environment_install(command: str) -> bool:
    """A plain `pip install <names>` / `-r requirements.txt` / `-e .` into the workspace's own environment (D-500): the one always-ask command a headless run may approve on request."""
    return bool(PIP_INSTALL.match(command)) and not INSTALL_REFUSED.search(command)


def auto_reply(event: Event, auto_approve: bool, allow_installs: bool = False) -> UserInput | None:
    payload = event.payload
    if event.type == EventType.APPROVAL_REQUESTED:
        if (
            allow_installs
            and auto_approve
            and payload.get("always_ask")
            and is_environment_install(str(payload.get("command") or ""))
        ):
            return Approve(request_id=payload["id"])
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


@dataclass
class BoxState:
    """What the deadline watcher has done, read by the main loop."""

    wrapping: bool = False  # the wrap-up has been decided: the loop must wait for its message
    wrap_sent: asyncio.Event = field(default_factory=asyncio.Event)
    hard_stopped: bool = False


POLL_SECONDS = 30  # how often the deadline watcher looks at the clock (tests make it small)


async def _sleep_until(moment: datetime, now: Callable[[], datetime]) -> None:
    while (left := (moment - now()).total_seconds()) > 0:
        await asyncio.sleep(min(left, POLL_SECONDS))


async def _watch_deadline(
    host: SessionHost, box: TimeBox, state: BoxState, now: Callable[[], datetime]
) -> None:
    """Soft deadline: interrupt the running turn (a queued message would wait behind it, perhaps for an hour) and send the wrap-up. Hard deadline: interrupt again and let the run end."""
    assert box.wrap_starts is not None and box.hard_stop is not None
    await _sleep_until(box.wrap_starts, now)
    state.wrapping = True
    await host.bus.publish(
        EventType.NOTICE,
        {"kind": "timebox", "text": f"Time box: wrapping up now (the run ends at {box.until:%H:%M})."},
    )
    if host.orchestrator is not None:
        host.orchestrator.wrap_up_mode = (
            True  # the wrap-up turn is the last: no next task is started after it
        )
    await host.submit(Interrupt())
    await asyncio.sleep(0.5)  # the cancelled turn unwinds before the next one starts
    await host.submit(SendMessage(text=box.wrap_message(now())))
    state.wrap_sent.set()
    await _sleep_until(box.hard_stop, now)
    state.hard_stopped = True
    await host.bus.publish(
        EventType.NOTICE, {"kind": "timebox", "text": f"Time box: stopped at {box.hard_stop:%H:%M}."}
    )
    await host.submit(Interrupt())


async def run_headless(
    host: SessionHost,
    requirement: str | None,
    auto_approve: bool,
    timebox: TimeBox | None = None,
    now: Callable[[], datetime] = datetime.now,
    allow_installs: bool = False,
) -> HeadlessResult:
    assert host.orchestrator is not None
    errors: list[str] = []
    installs: list[str] = []
    box_state = BoxState()
    watcher = (
        asyncio.create_task(_watch_deadline(host, timebox, box_state, now))
        if timebox is not None and timebox.until is not None
        else None
    )
    subscription = host.bus.subscribe(since_seq=host.bus.last_seq)
    if auto_approve:  # --auto-approve is the free-hand cadence (D-130) for the whole run
        host.orchestrator.set_cadence("free_hand")

    progress = [0]  # tool calls finished since the last nudge

    async def respond() -> None:
        async for event in subscription:
            if event.type == EventType.TOOL_CALL_FINISHED:
                progress[0] += 1
            if event.type == EventType.ERROR:
                errors.append(str(event.payload.get("message")))
            if allow_installs and event.type == EventType.APPROVAL_REQUESTED:
                command = str(event.payload.get("command") or "")
                if event.payload.get("always_ask") and is_environment_install(command):
                    installs.append(command)
            reply = (
                auto_reply(event, auto_approve, allow_installs=True)
                if allow_installs
                else auto_reply(event, auto_approve)
            )
            if reply is not None:
                await host.submit(reply)

    responder = asyncio.create_task(respond())
    engine = asyncio.create_task(host.run())
    try:
        if requirement:
            await host.submit(SendMessage(text=requirement))
        idle_nudges = 0
        for _ in range(MAX_TOTAL_NUDGES + 1):
            await _wait_until_idle(host)
            if box_state.wrapping and not box_state.wrap_sent.is_set():
                await (
                    box_state.wrap_sent.wait()
                )  # the interrupt just ended a turn; the wrap-up message is on its way
                await _wait_until_idle(host)
            if box_state.wrap_sent.is_set() or box_state.hard_stopped:
                break  # the time box decided
            idle_nudges = 0 if progress[0] else idle_nudges + 1
            progress[0] = 0
            if host.orchestrator.state.exported or errors or idle_nudges > MAX_PROCEED_NUDGES:
                break
            # The model asked something in plain text, or ended a turn with tasks still open.
            await host.submit(SendMessage(text=_proceed_text(host)))
        else:
            errors.append(f"stopped after {MAX_TOTAL_NUDGES} nudges to continue (runaway guard)")
        # Background work started by the orchestrator never blocks the user's turn; wait for it explicitly
        # here so a caller sees the settled state instead of racing it at close().
        if box_state.hard_stopped:
            with contextlib.suppress(TimeoutError):  # background work may not hold up a deadline
                await asyncio.wait_for(host.orchestrator.wait_idle(), 60)
        else:
            await host.orchestrator.wait_idle()
    finally:
        if watcher is not None:
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher
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
    summary = state.resume_summary()
    if (box_state.wrap_sent.is_set() or box_state.hard_stopped) and not errors and not state.exported:
        code = EXIT_TIMEBOX
        ended = "stopped at the hard limit" if box_state.hard_stopped else "wrapped up"
        summary = f"Time box: {ended}; the work is not finished. {summary}"
    return HeadlessResult(code, summary, tasks, errors, installs)


def _proceed_text(host: SessionHost) -> str:
    """The nudge; it names the open planned tasks so the model picks up the next one instead of summarising again."""
    assert host.orchestrator is not None
    open_tasks = [t for t in host.orchestrator.state.tasks if t.status in ("pending", "in_progress")]
    if not open_tasks:
        return PROCEED
    listed = "; ".join(f"{t.id} {t.title}" for t in open_tasks[:4])
    return f"{PROCEED} Tasks still open: {listed}. Work on them now with tools; do not stop to summarise until they are done or blocked."


async def _wait_until_idle(host: SessionHost) -> None:
    """Returns once no turn is running and nothing is queued."""
    await asyncio.sleep(0.2)
    while host.busy or not host.inputs_empty:
        await asyncio.sleep(0.2)
