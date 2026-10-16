"""Where did the time of one DebCraft run go? `python scripts/overnight/where_time_went.py <events.jsonl> [more files]`

Reads the event log of a run (.forge/transcripts/events.jsonl) and prints: the span of the run, the model calls by role and model (count, total and longest time), the slowest calls, the slowest tools,
how often each tool ran, the sub-agents with their time and tool calls, and every silence of more than a minute between two events. Used to find out why a job reached its time limit (the first overnight night's
"Two small briefs, arm A" ran 40 minutes). It prints no message text, only names and numbers."""

from __future__ import annotations

import itertools
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def when(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def read(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            continue
    return events


def clock(seconds: float) -> str:
    return f"{int(seconds // 60)}m{int(seconds % 60):02d}s"


def report(path: Path) -> str:
    events = read(path)
    if not events:
        return f"{path}: no events"
    start, end = when(events[0]["ts"]), when(events[-1]["ts"])
    out = [
        f"== {path}",
        f"span {clock((end - start).total_seconds())} from {start:%H:%M:%S} to {end:%H:%M:%S} UTC, {len(events)} events",
    ]

    calls = [e for e in events if e["type"] == "llm_call"]
    by_model: dict[tuple[str, str], list[float]] = defaultdict(list)
    for call in calls:
        payload = call["payload"]
        by_model[(payload.get("role", "?"), payload.get("model", "?"))].append(
            float(payload.get("latency_s") or 0)
        )
    out.append("\nmodel calls (role, model: count, total, longest)")
    for (role, model), times in sorted(by_model.items(), key=lambda item: -sum(item[1])):
        out.append(
            f"  {role:10} {model:14} {len(times):4} calls  total {clock(sum(times)):>8}  longest {clock(max(times))}"
        )
    out.append("slowest calls")
    for call in sorted(calls, key=lambda e: -float(e["payload"].get("latency_s") or 0))[:6]:
        p = call["payload"]
        usage = p.get("usage") or {}
        out.append(
            f"  {clock(float(p.get('latency_s') or 0)):>8} {p.get('role')}/{p.get('model')} out {usage.get('output_tokens')} reasoning {usage.get('reasoning_tokens')} in {usage.get('input_tokens')} -> {p.get('tool_calls') or p.get('finish_reason')}"
        )

    started: dict[str, tuple[str, datetime]] = {}
    spent: dict[str, list[float]] = defaultdict(list)
    for event in events:
        payload = event.get("payload", {})
        if event["type"] == "tool_call_started":
            started[payload.get("id", "")] = (payload.get("name", "?"), when(event["ts"]))
        elif event["type"] == "tool_call_finished" and payload.get("id") in started:
            name, begun = started.pop(payload["id"])
            spent[name].append((when(event["ts"]) - begun).total_seconds())
    out.append("\ntools (name: count, total, longest)")
    for name, times in sorted(spent.items(), key=lambda item: -sum(item[1]))[:10]:
        out.append(f"  {name:22} {len(times):4}  total {clock(sum(times)):>8}  longest {clock(max(times))}")

    agents = [e["payload"] for e in events if e["type"] == "agent_finished"]
    if agents:
        out.append("\nsub-agents (role: time, tool calls, failed)")
        for agent in agents:
            out.append(
                f"  {agent.get('id')} {agent.get('role')}: {clock(float(agent.get('duration_s') or 0))}, {agent.get('tool_calls')} tool calls, {agent.get('failed_calls')} failed"
            )
    steps = Counter(e["payload"].get("agent") for e in events if e["type"] == "subagent_step")
    if steps:
        out.append("sub-agent steps: " + ", ".join(f"{name} {count}" for name, count in steps.most_common(6)))

    out.append("\nsilences over a minute between two events")
    gaps = [
        (
            (when(after["ts"]) - when(before["ts"])).total_seconds(),
            before,
            after,
        )
        for before, after in itertools.pairwise(events)
    ]
    long_gaps = [gap for gap in gaps if gap[0] > 60]
    for seconds, before, after in sorted(long_gaps, key=lambda gap: -gap[0])[:8]:
        out.append(
            f"  {clock(seconds):>8} after {before['type']} {before.get('payload', {}).get('name', '')} at {when(before['ts']):%H:%M:%S}, before {after['type']}"
        )
    if not long_gaps:
        out.append("  none")
    repeats = Counter(
        f"{e['payload'].get('name')} {json.dumps(e['payload'].get('arguments'), sort_keys=True)[:80]}"
        for e in events
        if e["type"] == "tool_call_started"
    )
    again = [(count, key) for key, count in repeats.items() if count >= 4]
    if again:
        out.append("\nthe same tool call with the same arguments, 4 times or more")
        out += [f"  {count}x {key}" for count, key in sorted(again, reverse=True)[:6]]
    return "\n".join(out)


if __name__ == "__main__":
    for argument in sys.argv[1:]:
        print(report(Path(argument)))
        print()
