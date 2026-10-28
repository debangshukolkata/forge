"""D-538: a headless run keeps nudging while the model makes progress, and stops after two nudges in a row without any."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

from forge.engine import headless
from forge.engine.headless import EXIT_BLOCKED, run_headless
from forge.protocol.events import EventType
from forge.protocol.inputs import SendMessage


class ScriptedHost:
    """Each message starts a short turn that finishes `script[n]` tool calls; the run never exports, two tasks stay open."""

    def __init__(self, script: list[int]) -> None:
        self.script = script
        self.messages: list[str] = []
        self.busy = False
        self.queue: asyncio.Queue[Any] = asyncio.Queue()
        host = self

        class Subscription:
            def __aiter__(self) -> Any:
                return self

            async def __anext__(self) -> Any:
                return await host.queue.get()

            def close(self) -> None:
                return None

        self.bus = SimpleNamespace(last_seq=0, subscribe=lambda since_seq=0: Subscription())
        tasks = [
            SimpleNamespace(
                id="T4", title="Design system", status="in_progress", verification="", blocked_reason=""
            )
        ]
        tasks.append(
            SimpleNamespace(
                id="T5", title="Agent views", status="pending", verification="", blocked_reason=""
            )
        )
        state = SimpleNamespace(exported=False, tasks=tasks, resume_summary=lambda: "resumable")

        async def nothing() -> None:
            return None

        self.orchestrator = SimpleNamespace(state=state, set_cadence=lambda _c: None, wait_idle=nothing)

    @property
    def inputs_empty(self) -> bool:
        return True

    async def submit(self, user_input: Any) -> None:
        assert isinstance(user_input, SendMessage)
        self.messages.append(user_input.text)
        calls = self.script[len(self.messages) - 1] if len(self.messages) <= len(self.script) else 0
        self.busy = True
        for _ in range(calls):
            await self.queue.put(SimpleNamespace(type=EventType.TOOL_CALL_FINISHED, payload={}))
        await asyncio.sleep(0.05)
        self.busy = False

    async def run(self) -> None:
        await asyncio.sleep(3600)

    async def close(self) -> None:
        return None


async def test_a_model_that_keeps_working_is_nudged_past_the_old_limit_of_two() -> None:
    host = ScriptedHost([5, 3, 4, 2, 6])  # five turns with tool calls, then nothing
    result = await asyncio.wait_for(run_headless(host, "build it", True), 30)  # type: ignore[arg-type]
    # The first version stopped after the requirement and two nudges (3 messages) whatever the model did.
    assert (
        len(host.messages) == 5 + 3
    )  # five working turns, then three idle ones (two nudges in a row without progress)
    assert result.exit_code == EXIT_BLOCKED
    assert "T4 Design system" in host.messages[1] and "T5 Agent views" in host.messages[1]


async def test_a_model_that_does_nothing_stops_after_two_nudges() -> None:
    host = ScriptedHost([0])
    await asyncio.wait_for(run_headless(host, "build it", True), 30)  # type: ignore[arg-type]
    assert len(host.messages) == 3


async def test_the_runaway_guard_ends_an_endless_run(monkeypatch: Any) -> None:
    monkeypatch.setattr(headless, "MAX_TOTAL_NUDGES", 4)
    host = ScriptedHost([1] * 50)
    result = await asyncio.wait_for(run_headless(host, "build it", True), 30)  # type: ignore[arg-type]
    assert len(host.messages) == 1 + 5 and any("runaway guard" in error for error in result.errors)
