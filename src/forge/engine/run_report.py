"""Scrubbed run report you can send for analysis (TODO C17): the run summary plus per-agent cost, critic verdicts,
failed tool calls, errors and the task list. Built from events.jsonl only, so it holds no source code; secrets are
masked by the redactor and the user's folders and account name are replaced before anything is written."""

from __future__ import annotations

import getpass
import json
import re
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from forge.config import forge_home
from forge.engine.log_summary import summarize
from forge.protocol.events import Event, EventType, load_event_log
from forge.safety.redact import Redactor, default_redactor
from forge.toolkit import field_log
from forge.workspace.conversations import conversation_file

PREVIEW_CHARS = 140
VERDICT = re.compile(r"VERDICT:\s*(SHIP|REVISE)", re.IGNORECASE)
SCORE_LINE = re.compile(
    r"^\s*[-*]?\s*(hierarchy|consistency|polish|typography|states|responsive|distinctiveness)\b.*$",
    re.I | re.M,
)


def _scrubber(workspace: Path | None, redactor: Redactor) -> Callable[[str], str]:
    """Returns a function that masks secrets and replaces local folders and the account name."""
    replacements: list[tuple[str, str]] = []
    if workspace is not None:
        for form in {
            str(workspace),
            str(workspace.resolve()),
            workspace.as_posix(),
            workspace.resolve().as_posix(),
        }:
            replacements.append((form, "<workspace>"))
    home = Path.home()
    for form in {str(home), home.as_posix()}:
        replacements.append((form, "<home>"))
    with_user = getpass.getuser()
    replacements.sort(key=lambda pair: len(pair[0]), reverse=True)

    def scrub(text: str) -> str:
        text = redactor.redact(text)
        for old, new in replacements:
            text = text.replace(old, new)
        if with_user and len(with_user) > 2:
            text = re.sub(re.escape(with_user), "<user>", text, flags=re.IGNORECASE)
        return text

    return scrub


def _agent_table(events: list[Event]) -> list[str]:
    started = {e.payload.get("id"): e.payload for e in events if e.type == EventType.AGENT_STARTED}
    rows = []
    for event in events:
        if event.type != EventType.AGENT_FINISHED:
            continue
        payload = event.payload
        role = payload.get("role") or started.get(payload.get("id"), {}).get("role", "?")
        cost = payload.get("cost_usd")
        rows.append(
            f"| {role} | {'ok' if payload.get('ok') else 'FAILED'} | {payload.get('tool_calls', 0)} | "
            f"{payload.get('failed_calls', 0)} | {payload.get('duration_s', 0)}s | "
            f"{'' if cost is None else f'${float(cost):.3f}'} |"
        )
    if not rows:
        return []
    return [
        "## Subagents",
        "",
        "| Role | Result | Tool calls | Failed | Time | Cost |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
    ]


def _critic_section(events: list[Event]) -> list[str]:
    lines: list[str] = []
    for event in events:
        if event.type != EventType.TOOL_CALL_FINISHED or event.payload.get("name") != "spawn_subagent":
            continue
        preview = str(event.payload.get("preview", ""))
        verdict = VERDICT.search(preview)
        if not verdict:
            continue
        scores = [" ".join(m.group(0).split())[:100] for m in SCORE_LINE.finditer(preview)]
        lines.append(
            f"- {verdict.group(1).upper()} (event {event.seq})" + "".join(f"\n  - {s}" for s in scores[:7])
        )
    return ["## Critic and reviewer verdicts", "", *(lines or ["none recorded"]), ""]


def _failed_and_screens(events: list[Event]) -> list[str]:
    failed = [
        e.payload
        for e in events
        if e.type == EventType.TOOL_CALL_FINISHED
        and not e.payload.get("ok")
        and e.payload.get("name") != "spawn_subagent"
    ]
    shots = [e for e in events if e.type == EventType.NOTICE and e.payload.get("kind") == "screenshot"]
    out = [f"## Failed tool calls ({len(failed)})", ""]
    for item in failed[:30]:
        preview = " ".join(str(item.get("preview", "")).split())[:PREVIEW_CHARS]
        out.append(f"- {item.get('name')}: {str(item.get('summary', ''))[:80]} -> {preview}")
    out += ["", f"Screenshots taken: {len(shots)}", ""]
    return out


RUNNING_SYSTEM_TOOLS = ("http_request", "start_background", "memory_write", "memory_forget")


def _running_system_section(events: list[Event]) -> list[str]:
    """Every call that reaches or starts the system under test, in order and in full (D-634): the slowest-calls list cuts the address
    at 70 characters, which hid which endpoint a run called and what it started."""
    calls = [
        e
        for e in events
        if e.type == EventType.TOOL_CALL_FINISHED and e.payload.get("name") in RUNNING_SYSTEM_TOOLS
    ]
    if not calls:
        return []
    starts = [e for e in calls if e.payload.get("name") == "start_background"]
    others = [e for e in calls if e.payload.get("name") != "start_background"][-15:]
    shown = sorted({e.seq: e for e in [*starts[:6], *starts[-3:], *others]}.values(), key=lambda e: e.seq)
    out = ["## Calls to the running system, in order (what was started; the last calls)", ""]
    if len(starts) > 9:
        out.append(f"({len(starts)} start_background calls in all; the first 6 and the last 3 are listed)")
    for event in shown:
        payload = event.payload
        summary = " ".join(str(payload.get("summary", "")).split())[:400]
        result = " ".join(str(payload.get("preview", "")).split())[:200]
        out.append(
            f"- #{event.seq} {'ok' if payload.get('ok') else 'FAILED'} {payload.get('name')}: {summary}"
        )
        if result:
            out.append(f"  - returned: {result}")
    out.append("")
    return out


def _delivery_section(workspace: Path | None) -> list[str]:
    """The files the run would deliver (output/MANIFEST.json): names and status only. The closing line of a run counts
    deletions without naming them (D-639)."""
    if workspace is None:
        return []
    try:
        manifest = json.loads((workspace / "output" / "MANIFEST.json").read_text(encoding="utf-8"))
        files = [(str(f.get("status")), str(f.get("path"))) for f in manifest.get("files", [])]
    except (OSError, ValueError, AttributeError):
        return []
    if not files:
        return []
    order = {"deleted": 0, "modified": 1, "added": 2}
    files.sort(key=lambda item: (order.get(item[0], 3), item[1]))
    out = [f"## Files this run would deliver ({len(files)})", ""]
    out += [f"- {status}: {path}" for status, path in files[:40]]
    if len(files) > 40:
        out.append(f"- ... {len(files) - 40} more")
    return [*out, ""]


def _task_section(events: list[Event]) -> list[str]:
    last = next((e for e in reversed(events) if e.type == EventType.TASK_LIST_UPDATED), None)
    if last is None:
        return []
    out = ["## Task list at the end", ""]
    counts: dict[str, int] = defaultdict(int)
    for task in last.payload.get("tasks", []):
        counts[task.get("status", "?")] += 1
        out.append(f"- [{task.get('status')}] {task.get('title')} (attempts {task.get('attempts', 0)})")
        if task.get("blocked_reason"):
            out.append(f"  - blocked: {str(task['blocked_reason'])[:PREVIEW_CHARS]}")
    if not counts:  # a free-hand run plans no tasks; an empty "Totals:" read like a fault (LT1)
        out += ["No planned tasks (the run worked free hand).", ""]
        return out
    out += ["", "Totals: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())), ""]
    return out


def _seconds_between(first: str, last: str) -> float:
    try:
        return (datetime.fromisoformat(last) - datetime.fromisoformat(first)).total_seconds()
    except ValueError:
        return 0.0


def _timeline_section(events: list[Event]) -> list[str]:
    """Where the time went: wall clock, waiting for the model, running tools, a per-tool table and the slowest calls (TODO C17, needs the `duration_s` of S1)."""
    if not events:
        return []
    wall = _seconds_between(events[0].ts, events[-1].ts)
    model = sum(float(e.payload.get("latency_s") or 0) for e in events if e.type == EventType.LLM_CALL)
    finished = [
        e
        for e in events
        if e.type == EventType.TOOL_CALL_FINISHED and e.payload.get("duration_s") is not None
    ]
    by_tool: dict[str, list[float]] = defaultdict(list)
    by_phase: dict[str, float] = defaultdict(float)
    for event in finished:
        seconds = float(event.payload["duration_s"])
        by_tool[str(event.payload.get("name"))].append(seconds)
        by_phase[str((event.where or {}).get("phase") or "-")] += seconds
    tools = sum(sum(values) for values in by_tool.values())
    out = [
        "## Timeline",
        "",
        f"Wall clock {wall:.0f}s; model calls {model:.0f}s summed (subagents run in parallel, so this can exceed the wall clock); tools {tools:.0f}s summed.",
        "",
        "| Tool | Calls | Total s | Slowest s |",
        "|---|---|---|---|",
    ]
    for name, values in sorted(by_tool.items(), key=lambda item: -sum(item[1]))[:12]:
        out.append(f"| {name} | {len(values)} | {sum(values):.1f} | {max(values):.1f} |")
    out += [
        "",
        "Tool seconds by phase: "
        + (", ".join(f"{k} {v:.0f}s" for k, v in sorted(by_phase.items())) or "none"),
        "",
    ]
    slowest = sorted(finished, key=lambda e: -float(e.payload["duration_s"]))[:8]
    if slowest:
        out.append("Slowest calls:")
        out += [
            f"- #{e.seq} {e.payload.get('name')} {float(e.payload['duration_s']):.1f}s: {' '.join(str(e.payload.get('summary', '')).split())[:70]}"
            for e in slowest
        ]
        out.append("")
    return out


LAST_REQUEST_CHARS = 700
LAST_ANSWER_CHARS = 1800
FIELD_RECORDS_SHOWN = 25


def _what_happened(events: list[Event]) -> list[str]:
    """The top of the report (D-638): what was asked in the last turn, how it ended and what DebCraft said last, so the
    reader does not have to infer the outcome from counts. The final message is where DebCraft says what failed."""
    if not events:
        return []
    last_request = next((e for e in reversed(events) if e.type == EventType.USER_MESSAGE), None)
    start = events.index(last_request) if last_request else 0
    turn = events[start:]
    errors = [str(e.payload.get("message", "")) for e in turn if e.type == EventType.ERROR]
    failed = [e for e in turn if e.type == EventType.TOOL_CALL_FINISHED and not e.payload.get("ok")]
    done = [e for e in turn if e.type == EventType.MESSAGE_DONE]
    # D-639: the closing line the workflow adds ("Done: 4 task(s) completed ...") is a template, not the model's answer to
    # the user; report the last real message and the closing apart.
    answer = next((e for e in reversed(done) if e.payload.get("model") != "forge"), None)
    closing = next((e for e in reversed(done) if e.payload.get("model") == "forge"), None)
    asked = " ".join(str((last_request.payload if last_request else {}).get("text", "")).split())
    out = ["## What happened in the last request", ""]
    out.append(f"- Asked: {asked[:LAST_REQUEST_CHARS] or '(no user message)'}")
    out.append(f"- Started {turn[0].ts}, last event {turn[-1].ts}.")
    out.append(
        f"- Errors: {len(errors)}; failed tool calls: {len(failed)}; "
        + (
            "it ended with an answer."
            if answer
            else "it ended WITHOUT a final answer (stopped, or still running)."
        )
    )
    for message in errors[:5]:
        out.append(f"  - error: {' '.join(message.split())[:300]}")
    if answer:
        text = " ".join(str(answer.payload.get("text", "")).split())
        out += ["", "What DebCraft said last:", "", f"> {text[:LAST_ANSWER_CHARS]}"]
    if closing is not None:
        line = " ".join(str(closing.payload.get("text", "")).split())
        out += ["", f"Closing line added by the workflow (a template, not an answer): {line[:300]}"]
    return [*out, ""]


def _connection_section(events: list[Event], home: Path) -> list[str]:
    """The facts about connections and sign-ins since this conversation began (names, counts, seconds; never a value)."""
    since = events[0].ts if events else ""
    records = [r for r in field_log.read(home=home) if str(r.get("ts", "")) >= since[:19]]
    if not records:
        return []
    out = ["## Connection and sign-in facts since the conversation began (newest last)", ""]
    for record in records[-FIELD_RECORDS_SHOWN:]:
        rest = ", ".join(f"{k}={v}" for k, v in record.items() if k not in ("ts", "kind"))
        out.append(f"- {record.get('ts')} {record.get('kind')}: {rest}"[:300])
    return [*out, ""]


def build_run_report(
    events: list[Event],
    workspace: Path | None = None,
    redactor: Redactor = default_redactor,
    home: Path | None = None,
) -> str:
    """The whole report as markdown text, scrubbed."""
    parts = [
        *_what_happened(events),
        summarize(events),
        *_agent_table(events),
        *_timeline_section(events),
        *_critic_section(events),
        *_running_system_section(events),
        *_failed_and_screens(events),
        *_delivery_section(workspace),
        *_task_section(events),
        *_connection_section(events, home or forge_home()),
        "_Scrubbed: secrets masked, local folders and account name replaced, no source code included._",
    ]
    return _scrubber(workspace, redactor)("\n".join(parts) + "\n")


def write_run_report(
    workspace: Path, destination: Path | None = None, conversation: str | None = None
) -> Path:
    """Reads the event log of the active (or the named) conversation and writes the report next to it (or at `destination`)."""
    log = conversation_file(workspace, "events.jsonl", conversation)
    events = (
        load_event_log(log) if log.is_file() else []
    )  # a project that has not run yet still gets a (short) report
    target = destination or workspace / ".forge" / "run-report.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_run_report(events, workspace), encoding="utf-8")
    return target


def write_send_report(
    home: Path | None = None, workspace: Path | None = None, conversation: str | None = None
) -> Path | None:
    """The one report to send after a task that failed or went wrong (D-638): the newest project (or the named one),
    written to `<DebCraft Home>/reports/` with the time in its name, plus `latest.md` beside it. None: no project has a
    transcript yet."""
    from forge.engine.facts_report import newest_workspace

    base = home or forge_home()
    root = workspace or newest_workspace(base)
    if root is None:
        return None
    folder = base / "reports"
    target = folder / f"debcraft-report-{datetime.now():%Y%m%d-%H%M%S}.md"
    write_run_report(root, target, conversation)
    (folder / "latest.md").write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    return target
