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


def _tool(seq: int, name: str, summary: str, seconds: float, **payload: object) -> Event:
    fields = {"name": name, "ok": True, "summary": summary, "duration_s": seconds, **payload}
    return _event(seq, EventType.TOOL_CALL_FINISHED, seq, fields)


def test_failed_calls_are_listed_per_tool_with_the_most_common_reason() -> None:
    events = [
        _tool(1, "edit_file", "a.py", 0.1, ok=False, preview="Error: old_string was not found."),
        _tool(2, "edit_file", "b.py", 0.1, ok=False, preview="Error: old_string was not found."),
        _tool(3, "edit_file", "c.py", 0.1, ok=False, preview="Error: file is read-only"),
        _tool(4, "edit_file", "d.py", 0.1),
        _tool(5, "grep", "x", 0.1, ok=False, preview="bad regex"),
    ]
    report = summarize(events)
    assert 'edit_file: 3 failed of 4. Most common: "old_string was not found." x2' in report
    assert 'grep: 1 failed of 1. Most common: "bad regex" x1' in report
    assert report.index("edit_file: 3 failed") < report.index("grep: 1 failed")


def _llm(seq: int, input_tokens: int, cached: int, first_token: float | None) -> Event:
    payload: dict[str, object] = {
        "role": "coder",
        "latency_s": 5.0,
        "usage": {"input_tokens": input_tokens, "cached_input_tokens": cached},
    }
    if first_token is not None:
        payload["first_token_s"] = first_token
    return _event(seq, EventType.LLM_CALL, seq, payload)


def test_time_to_first_word_is_bucketed_by_input_size() -> None:
    events = [
        _llm(1, 10_000, 0, 1.0),
        _llm(2, 120_000, 60_000, 20.0),
        _llm(3, 130_000, 60_000, 40.0),
        _llm(4, 130_000, 0, None),
    ]
    report = summarize(events)
    assert "## Time to the first word by input size" in report
    assert "| under 25,000 | 1 | 1.0s | 1.0s | 0% |" in report
    assert "| 100,000 to 150,000 | 2 | 30.0s | 40.0s | 48% |" in report
    assert "50,000 to 100,000" not in report


def test_a_log_without_first_token_values_has_no_first_word_section() -> None:
    report = summarize([_llm(1, 10_000, 0, None)])
    assert "Time to the first word" not in report


def test_repeat_line_counts_all_repeats_and_pointers() -> None:
    events = [
        _tool(1, "read_file", "a.py", 0.1),
        _tool(2, "read_file", "a.py", 0.1, repeat_of=1),
        _tool(3, "read_file", "a.py", 0.1, repeat_of=1),
        _tool(4, "grep", "x", 0.1),
        _tool(5, "grep", "x", 0.1),
        _tool(6, "glob", "y", 0.1),
    ]
    report = summarize(events)
    assert "Calls that repeated an earlier one: 3 of 6; answered with a pointer: 2." in report


def _metrics(kind: str, outcome: str, view: float, **counts: object) -> dict[str, object]:
    return {"metrics": {"layer": "knowledge", "kind": kind, "outcome": outcome, "view_s": view, **counts}}


def test_summary_counts_knowledge_retrievals_inserts_and_refinements() -> None:
    events = [
        _event(1, EventType.SESSION_TIMING, 0, {"open_s": 0.8, "map_s": 2.5}),
        _tool(2, "knowledge_search", "knowledge_search search auth", 1.0, **_metrics("search", "whole", 0.4)),
        _tool(3, "knowledge_search", "knowledge_search search x", 3.0, **_metrics("search", "nothing", 2.6)),
        _tool(
            4,
            "knowledge_search",
            "knowledge_search read a,b",
            0.5,
            **_metrics("read", "read", 0.1, read=2, outdated=1),
        ),
        _tool(
            5, "knowledge_write", "knowledge_write a", 4.0, **_metrics("write", "written", 0.2, review_s=3.0)
        ),
        _tool(6, "knowledge_write", "knowledge_write a", 1.0, **_metrics("write", "corrected", 0.2)),
        _tool(7, "knowledge_write", "knowledge_write b", 1.0, **_metrics("write", "confirmed", 0.2)),
        _tool(8, "knowledge_write", "knowledge_write c", 1.0, **_metrics("write", "moved_to_memory", 0.2)),
        _tool(
            9,
            "code_map",
            "code_map env",
            2.0,
            **_metrics("code_map", "found", 1.5, action="env", files=1101),
        ),
    ]
    stored = {"topics": 6, "reads": 9, "search_hits": 12, "never_read": 2, "most_read": ["auth x5"]}
    report = summarize(events, stored)
    assert "2 searches (1 answered with a whole topic, 0 listed matches, 1 found nothing)" in report
    assert "1 read calls for 2 topics (1 of them marked outdated)" in report
    assert "Inserts: 1 new topics" in report
    assert "Refinements: 1 corrected, 1 confirmed still true, 0 removed" in report
    assert "1 moved to the project's memory" in report
    assert "Time in knowledge_write: 4 calls, 7.0s in all, 1.8s on average, slowest 4.0s" in report
    assert "of that 3.0s for the second model's check" in report
    assert "Time in code_map: 1 calls, 2.0s in all, 2.0s on average, slowest 2.0s (env x1)" in report
    assert "Bringing the index up to date, inside the calls above: 8 calls, 5.4s in all" in report
    assert "Source files in the index: 1101" in report
    assert "Opening the project: 1 calls, 0.8s in all" in report
    assert "Reading the repository map after the first screen: 1 calls, 2.5s" in report
    assert "6 topics, read 9 times and found by a search 12 times over all projects, 2 never read" in report


def test_knowledge_counts_are_read_from_an_older_log_without_metrics() -> None:
    events = [
        _tool(
            1,
            "knowledge_search",
            "knowledge_search search x",
            1.5,
            preview="Nothing written down matches 'x'.",
        ),
        _tool(
            2,
            "knowledge_write",
            "knowledge_write a",
            120.0,
            preview="Topic a written (3 source files tracked).",
        ),
        _tool(
            3,
            "knowledge_write",
            "knowledge_write a",
            90.0,
            preview="Topic a corrected (3 source files tracked).",
        ),
        _tool(4, "code_map", "code_map env", 70.0, preview="env file .env: A"),
    ]
    report = summarize(events)
    assert "1 searches (0 answered with a whole topic, 0 listed matches, 1 found nothing)" in report
    assert "Inserts: 1 new topics" in report
    assert "Refinements: 1 corrected" in report
    assert "slowest 120.0s" in report
    assert "4 of these calls are from before the tools reported their own numbers" in report


def test_a_log_without_knowledge_calls_has_no_knowledge_section() -> None:
    assert "Knowledge layer" not in summarize([_event(1, EventType.USER_MESSAGE, 0, {"text": "hi"})])


def test_old_log_without_llm_calls_says_so() -> None:
    report = summarize([_event(1, EventType.USER_MESSAGE, 0, {"text": "hi"})])
    assert "predates the run log" in report


def test_summary_separates_waiting_for_the_user_from_tool_time() -> None:
    events = [
        _event(1, EventType.USER_MESSAGE, 0, {"text": "install it"}),
        _event(
            2,
            EventType.TOOL_CALL_FINISHED,
            30,
            {"name": "run_command", "ok": True, "summary": "npm i", "duration_s": 5.0, "waited_s": 25.0},
        ),
    ]
    report = summarize(events)
    assert "tool calls: 1 (5s" in report
    assert "waiting for you (approvals, questions): 25s" in report
