"""One-page summary of a run from its events.jsonl (D-151): where the time went, what each model call cost,
which tools were slow or repeated. Read by the user and by the people tuning the agent loop, so it prints
facts only — no judgment about whether a run was good."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from forge.protocol.events import Event, EventType, load_event_log

SLOW_CALLS_SHOWN = 8


def _seconds_between(first: str, last: str) -> float:
    return (datetime.fromisoformat(last) - datetime.fromisoformat(first)).total_seconds()


def _split_turns(events: list[Event]) -> list[list[Event]]:
    turns: list[list[Event]] = []
    for event in events:
        if event.type == EventType.USER_MESSAGE or not turns:
            turns.append([])
        turns[-1].append(event)
    return turns


def _turn_line(index: int, turn: list[Event]) -> str:
    llm = [e.payload for e in turn if e.type == EventType.LLM_CALL]
    tools = [e.payload for e in turn if e.type == EventType.TOOL_CALL_FINISHED]
    wall = _seconds_between(turn[0].ts, turn[-1].ts) if len(turn) > 1 else 0.0
    llm_time = sum(c.get("latency_s", 0.0) for c in llm)
    tool_time = sum(t.get("duration_s", 0.0) for t in tools)
    first = next((e.payload.get("text", "") for e in turn if e.type == EventType.USER_MESSAGE), "")
    label = " ".join(str(first).split())[:60] or "(no user message)"
    cells = [str(index), label, f"{wall:.0f}s", str(len(llm)), f"{llm_time:.0f}s", str(len(tools))]
    return "| " + " | ".join([*cells, f"{tool_time:.0f}s"]) + " |"


def summarize(events: list[Event]) -> str:
    if not events:
        return "No events in this log."
    llm = [e.payload for e in events if e.type == EventType.LLM_CALL]
    tools = [e.payload for e in events if e.type == EventType.TOOL_CALL_FINISHED]
    out: list[str] = []
    wall = _seconds_between(events[0].ts, events[-1].ts)
    in_tokens = sum(c["usage"].get("input_tokens", 0) for c in llm)
    out_tokens = sum(c["usage"].get("output_tokens", 0) for c in llm)
    cached = sum(c["usage"].get("cached_input_tokens", 0) for c in llm)
    reasoning = sum(c["usage"].get("reasoning_tokens", 0) for c in llm)
    llm_time = sum(c.get("latency_s", 0.0) for c in llm)
    tool_time = sum(t.get("duration_s", 0.0) for t in tools)
    out += [
        "# Forge run summary",
        "",
        f"- Wall clock: {wall:.0f}s  |  model calls: {len(llm)} ({llm_time:.0f}s)  |  "
        f"tool calls: {len(tools)} ({tool_time:.0f}s, parallel calls overlap)",
        f"- Tokens: {in_tokens:,} in ({cached:,} cached), {out_tokens:,} out ({reasoning:,} reasoning)",
        "",
    ]
    if not llm:
        out += ["_No `llm_call` events: this log predates the run log (D-151)._", ""]

    out += [
        "## Per user message",
        "",
        "| # | Message | Wall | Model calls | Model time | Tools | Tool time |",
        "|---|---|---|---|---|---|---|",
    ]
    out += [_turn_line(i, turn) for i, turn in enumerate(_split_turns(events), 1)]

    by_role: dict[str, list[dict[str, Any]]] = {}
    for call in llm:
        by_role.setdefault(call.get("role", "?"), []).append(call)
    if by_role:
        out += [
            "",
            "## Model calls by role",
            "",
            "| Role | Model | Calls | Time | In tokens | Out tokens |",
            "|---|---|---|---|---|---|",
        ]
        for role, calls in sorted(by_role.items()):
            out.append(
                f"| {role} | {calls[0].get('model', '?')} | {len(calls)} | "
                f"{sum(c.get('latency_s', 0.0) for c in calls):.0f}s | "
                f"{sum(c['usage'].get('input_tokens', 0) for c in calls):,} | "
                f"{sum(c['usage'].get('output_tokens', 0) for c in calls):,} |"
            )
        out += ["", f"## Slowest model calls (top {SLOW_CALLS_SHOWN})", ""]
        for call in sorted(llm, key=lambda c: c.get("latency_s", 0.0), reverse=True)[:SLOW_CALLS_SHOWN]:
            asked = ", ".join(call.get("tool_calls", [])) or "text only"
            usage = call["usage"]
            out.append(
                f"- {call.get('latency_s', 0):.1f}s ({call.get('role')}, "
                f"first token {call.get('first_token_s')}s, "
                f"{usage.get('input_tokens', 0):,} in / {usage.get('output_tokens', 0):,} out, "
                f"{call.get('finish_reason')}) -> {asked}"
            )

    if tools:
        counts = Counter(t["name"] for t in tools)
        out += ["", "## Tools used", "", ", ".join(f"{name} x{n}" for name, n in counts.most_common())]
        out += ["", "## Slowest tool calls", ""]
        for tool in sorted(tools, key=lambda t: t.get("duration_s", 0.0), reverse=True)[:SLOW_CALLS_SHOWN]:
            status = "ok" if tool.get("ok") else "FAILED"
            out.append(
                f"- {tool.get('duration_s', 0):.1f}s {tool['name']} {status}: {tool.get('summary', '')[:90]}"
            )
        repeats = Counter((t["name"], t.get("summary", "")) for t in tools)
        repeated = [(key, n) for key, n in repeats.most_common() if n > 1][:SLOW_CALLS_SHOWN]
        if repeated:
            out += ["", "## Repeated identical tool calls", ""]
            out += [f"- x{n} {name}: {summary[:90]}" for (name, summary), n in repeated]
        failed = [t for t in tools if not t.get("ok")]
        out += ["", f"Failed tool calls: {len(failed)} of {len(tools)}."]

    notices = Counter(e.payload.get("kind", "?") for e in events if e.type == EventType.NOTICE)
    errors = [e.payload.get("message", "") for e in events if e.type == EventType.ERROR]
    agents = sum(1 for e in events if e.type == EventType.AGENT_STARTED)
    out += ["", "## Other", ""]
    out.append(f"- Subagents started: {agents}")
    out.append("- Notices: " + (", ".join(f"{k} x{n}" for k, n in notices.most_common()) or "none"))
    out.append(f"- Errors: {len(errors)}" + "".join(f"\n  - {m[:120]}" for m in errors[:5]))
    return "\n".join(out) + "\n"


def summarize_file(path: Path) -> str:
    return summarize(load_event_log(path))
