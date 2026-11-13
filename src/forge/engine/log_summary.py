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


KNOWLEDGE_TOOLS = ("knowledge_search", "knowledge_write", "code_map")
WRITE_OUTCOMES = (  # read from the result text of a log written before the tools reported metrics (D-575)
    ("Not saved as a topic", "moved_to_memory"),
    (" corrected (", "corrected"),
    (" written (", "written"),
    (" confirmed against", "confirmed"),
    (" removed.", "removed"),
)


def _knowledge_call(payload: dict[str, Any]) -> dict[str, Any] | None:
    """One call of a knowledge tool as {kind, outcome, seconds, ...}. The tool's own `metrics` when the log has
    them; for an older log the kind comes from the call's summary and the outcome from its result text."""
    name = str(payload.get("name"))
    if name not in KNOWLEDGE_TOOLS:
        return None
    seconds = float(payload.get("duration_s") or 0.0)
    metrics = payload.get("metrics")
    if isinstance(metrics, dict) and metrics.get("layer") == "knowledge":
        return {**metrics, "seconds": seconds, "measured": True}
    words = str(payload.get("summary", "")).split()
    action = words[1] if len(words) > 1 else "?"
    preview = str(payload.get("preview", ""))
    if name == "code_map":
        return {"kind": "code_map", "action": action, "outcome": "?", "seconds": seconds}
    if name == "knowledge_write":
        outcome = next((label for mark, label in WRITE_OUTCOMES if mark in preview), "refused")
        return {"kind": "write", "outcome": outcome, "seconds": seconds}
    if not payload.get("ok"):
        outcome = "missing" if action == "read" else "refused"
    elif action == "search":
        nothing = preview.startswith("Nothing written down matches")
        outcome = "nothing" if nothing else "whole" if ", in full:" in preview else "matches"
    else:
        outcome = "read" if action == "read" else "listed"
    return {"kind": action, "outcome": outcome, "seconds": seconds, "read": 1 if outcome == "read" else 0}


def _timing(seconds: list[float]) -> str:
    if not seconds:
        return "0 calls"
    return (
        f"{len(seconds)} calls, {sum(seconds):.1f}s in all, {sum(seconds) / len(seconds):.1f}s on average, "
        f"slowest {max(seconds):.1f}s"
    )


def knowledge_section(events: list[Event], stored: dict[str, Any] | None = None) -> list[str]:
    """What the knowledge layer did in this log (D-575): retrievals, new topics, refinements, and the seconds
    they and the index took. `stored`: what is on disk for the repository now, when a workspace was given."""
    calls = [
        call
        for event in events
        if event.type == EventType.TOOL_CALL_FINISHED
        for call in [_knowledge_call(event.payload)]
        if call is not None
    ]
    opens = [e.payload for e in events if e.type == EventType.SESSION_TIMING]
    if not calls and not opens and not stored:
        return []
    out = ["", "## Knowledge layer", ""]

    def of(kind: str) -> list[dict[str, Any]]:
        return [call for call in calls if call["kind"] == kind]

    def count(found: list[dict[str, Any]], outcome: str) -> int:
        return sum(1 for call in found if call["outcome"] == outcome)

    searches, reads, writes, maps = of("search"), of("read"), of("write"), of("code_map")
    whole = count(searches, "whole")
    out.append(
        f"- Retrievals: {len(searches)} searches ({whole} answered with a whole topic, "
        f"{count(searches, 'matches')} listed matches, {count(searches, 'nothing')} found nothing); "
        f"{len(reads)} read calls for {sum(int(call.get('read', 0)) for call in reads)} topics "
        f"({sum(int(call.get('outdated', 0)) for call in reads)} of them marked outdated); "
        f"{len(of('list'))} list, {len(of('agenda'))} agenda"
    )
    out.append(f"- Inserts: {count(writes, 'written')} new topics")
    out.append(
        f"- Refinements: {count(writes, 'corrected')} corrected, {count(writes, 'confirmed')} confirmed "
        f"still true, {count(writes, 'removed')} removed"
    )
    out.append(
        f"- Not saved as a topic: {count(writes, 'moved_to_memory')} moved to the project's memory (about the "
        f"task, not the repository), {count(writes, 'refused')} refused"
    )
    out.append(
        f"- Time in knowledge_search: {_timing([c['seconds'] for c in calls if c['kind'] in ('search', 'read', 'list', 'agenda')])}"
    )
    review = sum(float(call.get("review_s", 0.0)) for call in writes)
    out.append(
        f"- Time in knowledge_write: {_timing([call['seconds'] for call in writes])}"
        + (f" (of that {review:.1f}s for the second model's check)" if review else "")
    )
    actions = Counter(str(call.get("action", "?")) for call in maps)
    out.append(
        f"- Time in code_map: {_timing([call['seconds'] for call in maps])}"
        + (" (" + ", ".join(f"{name} x{n}" for name, n in actions.most_common()) + ")" if maps else "")
    )
    measured = [call for call in calls if call.get("measured")]
    if measured:
        out.append(
            "- Bringing the index up to date, inside the calls above: "
            + _timing([float(call.get("view_s", 0.0)) for call in measured])
        )
        sizes = [int(call["files"]) for call in measured if call.get("files")]
        if sizes:
            out.append(f"- Source files in the index: {max(sizes)}")
    if len(measured) < len(calls):
        out.append(
            f"- {len(calls) - len(measured)} of these calls are from before the tools reported their own "
            "numbers: their outcome is read from the result text and they have no index time."
        )
    if opens:
        out.append("- Opening the project: " + _timing([float(o.get("open_s", 0.0)) for o in opens]))
        maps_read = [float(o["map_s"]) for o in opens if o.get("map_s") is not None]
        if maps_read:
            out.append("- Reading the repository map after the first screen: " + _timing(maps_read))
    if stored:
        top = ", ".join(stored.get("most_read", [])) or "none read yet"
        out.append(
            f"- On disk for this repository now: {stored.get('topics', 0)} topics, read {stored.get('reads', 0)} "
            f"times and found by a search {stored.get('search_hits', 0)} times over all projects, "
            f"{stored.get('never_read', 0)} never read. Most read: {top}"
        )
    return out


FAILURES_SHOWN = 10
FIRST_WORD_BUCKETS = (
    ("under 25,000", 0, 25_000),
    ("25,000 to 50,000", 25_000, 50_000),
    ("50,000 to 100,000", 50_000, 100_000),
    ("100,000 to 150,000", 100_000, 150_000),
    ("over 150,000", 150_000, float("inf")),
)


def _failure_reason(preview: Any) -> str:
    text = str(preview).strip()
    if text.startswith("Error: "):
        text = text[len("Error: ") :]
    return text[:80]


def _failures_by_tool(tools: list[dict[str, Any]]) -> list[str]:
    """Per tool: how many calls failed and the most common reason (HW0)."""
    failed_by_tool: dict[str, list[str]] = {}
    for tool in tools:
        if not tool.get("ok"):
            failed_by_tool.setdefault(str(tool.get("name")), []).append(
                _failure_reason(tool.get("preview", ""))
            )
    totals = Counter(str(t.get("name")) for t in tools)
    lines = []
    for name, reasons in sorted(failed_by_tool.items(), key=lambda item: -len(item[1]))[:FAILURES_SHOWN]:
        reason, times = Counter(reasons).most_common(1)[0]
        lines.append(f'- {name}: {len(reasons)} failed of {totals[name]}. Most common: "{reason}" x{times}')
    return lines


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _first_word_section(llm: list[dict[str, Any]]) -> list[str]:
    """Time to the first word by input size, to show where a long history starts to cost seconds (HW0)."""
    timed = [c for c in llm if c.get("first_token_s") is not None]
    if not timed:
        return []
    out = [
        "",
        "## Time to the first word by input size",
        "",
        "| Input tokens | Calls | Median first word | Slowest | Cached share |",
        "|---|---|---|---|---|",
    ]
    for label, low, high in FIRST_WORD_BUCKETS:
        found = [c for c in timed if low <= c["usage"].get("input_tokens", 0) < high]
        if not found:
            continue
        seconds = [float(c["first_token_s"]) for c in found]
        total = sum(c["usage"].get("input_tokens", 0) for c in found)
        cached = sum(c["usage"].get("cached_input_tokens", 0) for c in found)
        share = f"{100 * cached / total:.0f}%" if total else "0%"
        out.append(f"| {label} | {len(found)} | {_median(seconds):.1f}s | {max(seconds):.1f}s | {share} |")
    return out


def summarize(events: list[Event], stored_knowledge: dict[str, Any] | None = None) -> str:
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
    user_wait = sum(t.get("waited_s", 0.0) for t in tools)
    out += [
        "# DebCraft run summary",
        "",
        f"- Wall clock: {wall:.0f}s  |  model calls: {len(llm)} ({llm_time:.0f}s)  |  "
        f"tool calls: {len(tools)} ({tool_time:.0f}s, parallel calls overlap)  |  "
        f"waiting for you (approvals, questions): {user_wait:.0f}s",
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
        all_repeated = [(key, n) for key, n in repeats.most_common() if n > 1]
        repeated = all_repeated[:SLOW_CALLS_SHOWN]
        if repeated:
            wasted = sum(n - 1 for _, n in all_repeated)
            pointers = sum(1 for t in tools if t.get("repeat_of"))
            out += ["", "## Repeated identical tool calls", ""]
            out.append(
                f"Calls that repeated an earlier one: {wasted} of {len(tools)}; "
                f"answered with a pointer: {pointers}."
            )
            out += [f"- x{n} {name}: {summary[:90]}" for (name, summary), n in repeated]
        failed = [t for t in tools if not t.get("ok")]
        out += ["", f"Failed tool calls: {len(failed)} of {len(tools)}."]
        out += _failures_by_tool(tools)

    out += _first_word_section(llm)

    out += knowledge_section(events, stored_knowledge)

    notices = Counter(e.payload.get("kind", "?") for e in events if e.type == EventType.NOTICE)
    errors = [e.payload.get("message", "") for e in events if e.type == EventType.ERROR]
    agents = sum(1 for e in events if e.type == EventType.AGENT_STARTED)
    out += ["", "## Other", ""]
    out.append(f"- Subagents started: {agents}")
    out.append("- Notices: " + (", ".join(f"{k} x{n}" for k, n in notices.most_common()) or "none"))
    out.append(f"- Errors: {len(errors)}" + "".join(f"\n  - {m[:120]}" for m in errors[:5]))
    return "\n".join(out) + "\n"


def summarize_file(path: Path, stored_knowledge: dict[str, Any] | None = None) -> str:
    return summarize(load_event_log(path), stored_knowledge)
