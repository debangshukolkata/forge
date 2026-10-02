"""Run-log summary (D-151): deterministic parsing of an events.jsonl, no model involved."""

from __future__ import annotations

from forge.engine.log_summary import summarize
from forge.protocol.events import Event, EventType


def _event(seq: int, kind: EventType, second: int, payload: dict[str, object]) -> Event:
    return Event(seq=seq, type=kind, ts=f"2026-10-02T10:00:{second:02d}.000+00:00", payload=payload)


def test_summary_reports_time_tokens_and_repeats() -> None:
    usage = {"input_tokens": 1000, "output_tokens": 50, "cached_input_tokens": 400, "reasoning_tokens": 20}
    events = [
        _event(1, EventType.USER_MESSAGE, 0, {"text": "fix the flicker"}),
        _event(
            2,
            EventType.LLM_CALL,
            4,
            {
                "role": "coder",
                "model": "gpt",
                "latency_s": 4.0,
                "first_token_s": 1.5,
                "finish_reason": "tool_calls",
                "usage": usage,
                "tool_calls": ["read_file"],
            },
        ),
        _event(
            3,
            EventType.TOOL_CALL_FINISHED,
            5,
            {"name": "read_file", "ok": True, "summary": "a.tsx", "duration_s": 0.1},
        ),
        _event(
            4,
            EventType.TOOL_CALL_FINISHED,
            6,
            {"name": "read_file", "ok": False, "summary": "a.tsx", "duration_s": 0.2},
        ),
    ]
    report = summarize(events)
    assert "model calls: 1 (4s)" in report
    assert "1,000 in (400 cached)" in report
    assert "| 1 | fix the flicker |" in report
    assert "x2 read_file: a.tsx" in report
    assert "Failed tool calls: 1 of 2" in report


def test_old_log_without_llm_calls_says_so() -> None:
    report = summarize([_event(1, EventType.USER_MESSAGE, 0, {"text": "hi"})])
    assert "predates the run log" in report
