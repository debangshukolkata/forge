"""Reading a streamed answer by event (RS9, D-599).

An agent API often answers as a stream: server-sent events (`event:` and `data:` lines) or one JSON object per line.
Waiting for the end and handing the model the whole text hides what it needs: which tool calls the agent made and in
what order, where it stalled, whether an error came in the middle, and what the final answer was. This turns the
lines of a stream, each with the second it arrived, into a short account. Pure functions, no network."""

from __future__ import annotations

import contextlib
import itertools
import json
from dataclasses import dataclass
from typing import Any

KIND_KEYS = ("type", "event", "kind", "stage", "status")
TOOL_NAME_KEYS = ("name", "tool", "tool_name", "function")
FINAL_KINDS = (
    "final",
    "answer",
    "done",
    "complete",
    "completed",
    "result",
    "end",
    "finish",
    "finished",
    "message",
)
DELTA_KINDS = ("delta", "token", "chunk", "partial", "text")
MAX_KINDS = 12
MAX_TOOLS = 25
MAX_ERRORS = 3
ANSWER_CHARS = 600


@dataclass
class StreamEvent:
    at: float  # seconds since the request was sent
    kind: str
    payload: Any  # parsed JSON, or the text of the data line
    size: int  # characters of the data


def parse_stream(items: list[tuple[float, str]]) -> list[StreamEvent]:
    """Events of a stream given as (seconds, line). Server-sent events end at a blank line; a stream without
    `data:` lines is read as one JSON object per line, and a line that is no JSON at all counts as text."""
    events: list[StreamEvent] = []
    sse = any(line.startswith(("data:", "event:")) for _, line in items)
    name = ""
    data: list[str] = []
    started = 0.0

    def flush() -> None:
        nonlocal name, data
        if not data and not name:
            return
        text = "\n".join(data)
        events.append(_event(started, name, text))
        name, data = "", []

    for at, line in items:
        if not sse:
            if line.strip():
                events.append(_event(at, "", line.strip()))
            continue
        if not line.strip():
            flush()
        elif line.startswith("event:"):
            if not data and not name:
                started = at
            name = line[6:].strip()
        elif line.startswith("data:"):
            if not data and not name:
                started = at
            data.append(line[5:].lstrip())
        # comment lines (":") and fields such as `id:` carry nothing for the account
    flush()
    return events


def _event(at: float, sse_name: str, text: str) -> StreamEvent:
    payload: Any = text
    with contextlib.suppress(ValueError):  # not JSON: the text itself is the payload
        payload = json.loads(text)
    kind = sse_name
    if not kind and isinstance(payload, dict):
        kind = next((str(payload[key]) for key in KIND_KEYS if isinstance(payload.get(key), str)), "")
    return StreamEvent(at=at, kind=kind or "data", payload=payload, size=len(text))


def _text_of(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("text", "answer", "content", "message", "output", "result", "delta", "token"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
            if isinstance(value, dict):
                inner = _text_of(value)
                if inner:
                    return inner
    return ""


def _is_tool(event: StreamEvent) -> bool:
    kind = event.kind.lower()
    if "tool" in kind or "function" in kind:
        return True
    return isinstance(event.payload, dict) and any(key in event.payload for key in ("tool", "tool_name"))


def _tool_label(event: StreamEvent) -> str:
    payload = event.payload
    name = ""
    if isinstance(payload, dict):
        name = next((str(payload[key]) for key in TOOL_NAME_KEYS if isinstance(payload.get(key), str)), "")
    return f"{event.kind} {name}".strip()


def summarize_stream(items: list[tuple[float, str]], total_seconds: float, cut: bool = False) -> list[str]:
    """The account of a stream as lines of text for the model."""
    events = parse_stream(items)
    if not events:
        return [f"Stream: no events in {total_seconds:.1f} s."]
    counts: dict[str, int] = {}
    for event in events:
        counts[event.kind] = counts.get(event.kind, 0) + 1
    kinds = ", ".join(f"{kind} x{n}" for kind, n in sorted(counts.items(), key=lambda kv: -kv[1])[:MAX_KINDS])
    lines = [
        f"Stream: {len(events)} events in {total_seconds:.1f} s (first after {events[0].at:.1f} s)"
        + (", cut at the time limit" if cut else "")
        + f". Kinds: {kinds}."
    ]
    tools = [event for event in events if _is_tool(event)]
    if tools:
        lines.append("Tool events in order:")
        for event in tools[:MAX_TOOLS]:
            lines.append(f"- {event.at:6.1f} s  {_tool_label(event)} ({event.size:,} characters)")
        if len(tools) > MAX_TOOLS:
            lines.append(f"- ... {len(tools) - MAX_TOOLS} more")
    if len(events) > 1:
        gap, before = max(((b.at - a.at, b) for a, b in itertools.pairwise(events)), key=lambda x: x[0])
        if gap >= 2.0:
            lines.append(f"Longest silence: {gap:.1f} s before the {before.kind} event at {before.at:.1f} s.")
    errors = [
        event
        for event in events
        if "error" in event.kind.lower() or (isinstance(event.payload, dict) and event.payload.get("error"))
    ]
    for event in errors[:MAX_ERRORS]:
        detail = _text_of(event.payload) or (
            str(event.payload.get("error")) if isinstance(event.payload, dict) else str(event.payload)
        )
        lines.append(f"Error event at {event.at:.1f} s: {detail[:200]}")
    final = next(
        (e for e in reversed(events) if e.kind.lower() in FINAL_KINDS and _text_of(e.payload)),
        None,
    )
    answer = _text_of(final.payload) if final else ""
    if (
        not answer
    ):  # no explicit final event: the pieces of a token stream joined, or the last event with text
        pieces = [_text_of(e.payload) for e in events if e.kind.lower() in DELTA_KINDS]
        answer = "".join(piece for piece in pieces if piece) or next(
            (_text_of(e.payload) for e in reversed(events) if _text_of(e.payload)), ""
        )
    if answer:
        shown = answer[:ANSWER_CHARS] + ("..." if len(answer) > ANSWER_CHARS else "")
        lines.append(f"Final answer ({len(answer):,} characters): {shown}")
    else:
        lines.append("No final answer text was found in the stream.")
    return lines
