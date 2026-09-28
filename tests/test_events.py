from __future__ import annotations

import asyncio
import json
from pathlib import Path

from forge.engine.events import EventBus, EventType
from forge.engine.inputs import Answer, Interrupt, parse_user_input
from forge.safety.redact import Redactor


async def test_events_are_numbered_and_persisted(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    bus = EventBus(log, redactor=Redactor())

    await bus.publish(EventType.STATUS_CHANGED, {"state": "idle"})
    await bus.publish(EventType.MESSAGE_DONE, {"text": "hi"})

    lines = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [line["seq"] for line in lines] == [1, 2]
    assert lines[1]["type"] == "message_done"


async def test_reopened_log_continues_the_sequence(tmp_path: Path) -> None:
    log = tmp_path / "events.jsonl"
    first = EventBus(log, redactor=Redactor())
    await first.publish(EventType.NOTICE, {"text": "a"})

    second = EventBus(log, redactor=Redactor())
    event = await second.publish(EventType.NOTICE, {"text": "b"})

    assert event.seq == 2
    assert [e.payload["text"] for e in second.events_since(0)] == ["a", "b"]


async def test_subscriber_replays_then_receives_live_events() -> None:
    bus = EventBus(redactor=Redactor())
    for text in ("one", "two", "three"):
        await bus.publish(EventType.NOTICE, {"text": text})

    subscription = bus.subscribe(since_seq=1)  # a UI that already saw event 1 reconnects
    await bus.publish(EventType.NOTICE, {"text": "four"})
    received = [(await asyncio.wait_for(subscription.__anext__(), 1)).payload["text"] for _ in range(3)]
    subscription.close()

    assert received == ["two", "three", "four"]


async def test_payloads_are_redacted_before_storage(tmp_path: Path) -> None:
    redactor = Redactor()
    redactor.register("canary-secret-555555", "CANARY")
    log = tmp_path / "events.jsonl"
    bus = EventBus(log, redactor=redactor)

    await bus.publish(EventType.MESSAGE_DELTA, {"text": "leaked canary-secret-555555?"})

    assert "canary-secret-555555" not in log.read_text(encoding="utf-8")
    assert bus.events_since(0)[0].payload["text"] == "leaked [REDACTED:CANARY]?"


def test_inputs_parse_from_json() -> None:
    assert isinstance(parse_user_input({"kind": "interrupt"}), Interrupt)
    answer = parse_user_input({"kind": "answer", "question_id": "q1", "choice": "B"})
    assert isinstance(answer, Answer) and answer.choice == "B"
