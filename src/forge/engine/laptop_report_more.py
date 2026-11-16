"""`forge laptop report`: the two pages for the laptop items that had no verdict (LP5, D-625).

`calls_page`: what went out of the machine (TK6: calls DebCraft signed in for by itself; HT1: HTTP calls by kind of host and refused tokens; RS9: streamed
answers; TV1: Tavily; SF2: a settings file written through the red card, then a sign-in). `delivery_page`: what
was delivered and what the index cost (WF2: temporary changes and the leftover review; KP8: library folders in the
delivery; KP7: seconds per knowledge tool call; KP0: the sizes). Names, counts and seconds only, as on every page.
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from forge.config import forge_home
from forge.engine.laptop_pages import Page, Verdict
from forge.engine.laptop_report import EDITING, Call, Conversation
from forge.protocol.events import Event, EventType
from forge.toolkit import field_log

LOCAL = {"localhost", "127.0.0.1", "[::1]", "::1", "0.0.0.0"}
TAVILY = ("tavily_research", "tavily_extract", "tavily_crawl")
KNOWLEDGE = ("code_map", "knowledge_search", "knowledge_write")
LIBRARY_FOLDERS = {
    ".vendor",
    "site-packages",
    "node_modules",
    ".venv",
    "venv",
    ".nox",
    ".eggs",
    "__pycache__",
}
STREAM_EVENTS = re.compile(r"Stream: (\d+) events in ([\d.]+) s")
NAME_GONE = "DEVELOPMENT_INSTANCE_TOKEN"  # not read since D-626
SLOW_INDEX_S = 10.0
MAX_WALK = 20000


def _host(call: Call) -> str:
    address = next((part for part in call.argument("url").split() if part.startswith("http")), "")
    return (urlparse(address).hostname or "").lower()


def _notices(events: list[Event], kind: str) -> list[Event]:
    return [e for e in events if e.type == EventType.NOTICE and e.payload.get("kind") == kind]


def _local_time(stamp: str) -> datetime | None:
    """An event's time as the field log writes its own (local, no zone), so the two can be put in order."""
    try:
        found = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return found.astimezone().replace(tzinfo=None) if found.tzinfo else found


def _http_lines(page: Page, calls: list[Call], home: Path) -> None:
    from forge.toolkit.app_logins import load_logins

    try:
        logins = list(load_logins(home).values())
    except Exception:  # the sign-in page reports a broken file; here it only means no host is listed
        logins = []
    listed = {login.host: login.name for login in logins}
    listed_tokens = {login.token_name for login in logins}
    http = [c for c in calls if c.name == "http_request"]
    groups: dict[str, list[Call]] = {"this machine": [], "listed": [], "other": []}
    for call in http:
        host = _host(call)
        groups["this machine" if host in LOCAL else "listed" if host in listed else "other"].append(call)
    for label, found in groups.items():
        answered = sum(1 for c in found if c.status() is not None)
        with_token = sum(1 for c in found if c.argument("token_env"))
        page.lines.append(
            f"http_request to {label}: {len(found)} calls, {answered} answered, {with_token} with a token name"
        )
    others = Counter(_host(c) for c in groups["other"])
    if others:
        page.lines.append("   other hosts: " + ", ".join(f"{h} x{n}" for h, n in others.most_common(4)))
    refused = [c for c in http if "a token goes only to this machine" in c.preview]
    page.lines.append(f"   token refused for a host that is not listed: {len(refused)}x")
    leaked = [c for c in groups["other"] if c.argument("token_env") and c.status() is not None]
    remote = groups["listed"] + groups["other"]
    answered_listed = sum(1 for c in groups["listed"] if c.status() is not None)
    page.verdicts.append(
        Verdict("HT1", "NOT RUN", "no http_request to another machine yet")
        if not remote
        else Verdict(
            "HT1", "FAIL", f"{len(leaked)} call(s) with a token name reached a host that is not listed"
        )
        if leaked
        else Verdict(
            "HT1",
            "PASS" if answered_listed else "CHECK",
            f"listed hosts answered {answered_listed}x, other hosts {len(groups['other'])}x, "
            f"token refused {len(refused)}x",
        )
    )

    signed = [c for c in http if "DebCraft signed in to" in c.preview]
    fixed = Counter(
        c.argument("token_env") for c in http if c.argument("token_env") not in listed_tokens | {""}
    )
    asked = sum(
        1 for c in http if "Do not ask the user for a token" in c.preview or "could not sign in" in c.preview
    )
    page.lines.append(
        f"calls DebCraft signed in for by itself: {len(signed)} (this machine "
        f"{sum(1 for c in signed if _host(c) in LOCAL)}); left without a token: {asked}; fixed token names "
        f"used: {dict(fixed) or 'none'}"
    )
    page.verdicts.append(
        Verdict("TK6", "NOT RUN", "no call was answered 401 yet, so nothing had to sign in")
        if not signed and not asked
        else Verdict(
            "TK6",
            "PASS" if signed and not asked and NAME_GONE not in fixed else "CHECK",
            f"signed in by itself {len(signed)}x, left without a token {asked}x, fixed names {list(fixed) or 'none'}",
        )
    )

    streams = [c for c in http if c.arguments and isinstance(c.arguments, dict) and c.arguments.get("stream")]
    counted = [found for c in streams for found in [STREAM_EVENTS.search(c.preview)] if found]
    page.lines.append(
        f"streamed calls: {len(streams)}, ok {sum(1 for c in streams if c.ok)}; events "
        + (", ".join(f"{m.group(1)} in {m.group(2)}s" for m in counted[:4]) or "none counted")
    )
    no_answer = sum(1 for c in streams if "No final answer text" in c.preview)
    page.verdicts.append(
        Verdict("RS9", "NOT RUN", "no http_request with stream yet; do step 7")
        if not streams
        else Verdict(
            "RS9",
            "PASS" if counted and not no_answer and all(c.ok for c in streams) else "CHECK",
            f"{len(streams)} streamed, events counted in {len(counted)}, no final answer in {no_answer}",
        )
    )


def calls_page(conversations: list[Conversation], home: Path | None = None) -> Page:
    """HT1, RS9, TV1 and SF2: what went out of the machine, and the settings file written on a red card."""
    home = home or forge_home()
    page = Page("CALLS OUT: HTTP, STREAMS, TAVILY, SETTINGS FILES")
    calls = [call for c in conversations for call in c.calls]
    events = [e for c in conversations for e in c.events]
    _http_lines(page, calls, home)

    tavily = [c for c in calls if c.name in TAVILY]
    for name in TAVILY:
        mine = [c for c in tavily if c.name == name]
        failed = [c for c in mine if not c.ok]
        page.lines.append(
            f"{name}: {len(mine)} calls, ok {len(mine) - len(failed)}"
            + (f"; last failure: {' '.join(failed[-1].preview.split())[:60]}" if failed else "")
        )
    crawl_ok = any(c.ok for c in tavily if c.name == "tavily_crawl")
    page.verdicts.append(
        Verdict("TV1", "NOT RUN", "no Tavily research, extract or crawl call yet; do step 7")
        if not tavily
        else Verdict(
            "TV1",
            "PASS" if crawl_ok and all(c.ok for c in tavily) else "CHECK",
            f"crawl ok: {crawl_ok}; failed {sum(1 for c in tavily if not c.ok)} of {len(tavily)}",
        )
    )

    writes = [c for c in calls if c.name == "settings_file" and c.argument("action") == "write"]
    written = _notices(events, "settings_file")
    files = Counter(c.argument("file") for c in writes)
    page.lines.append(
        f"settings_file writes asked: {len(writes)} {dict(files)}; approved and written: {len(written)}"
    )
    for call in [c for c in writes if not c.ok][-2:]:
        page.lines.append(f"   not written: {' '.join(call.preview.split())[:84]}")
    logins_written = [
        e for e in written if "app_logins.yaml" in str(e.payload.get("text", "")) and _local_time(e.ts)
    ]
    signed_in_after = 0
    if logins_written:
        at = _local_time(logins_written[-1].ts)
        for record in field_log.read(("sign_in",), home):
            when = _local_time(str(record.get("ts", "")))
            signed_in_after += bool(record.get("ok") and when and at and when >= at)
        page.lines.append(f"   successful sign-ins after app_logins.yaml was written: {signed_in_after}")
    page.verdicts.append(
        Verdict("SF2", "NOT RUN", "app_logins.yaml was not written through settings_file; do step 7")
        if not logins_written
        else Verdict("SF2", "PASS", f"written on a red card, {signed_in_after} sign-in(s) after it")
        if signed_in_after
        else Verdict("SF2", "CHECK", "written on a red card, no successful sign-in after it yet")
    )
    return page


def _files_under(folder: Path) -> tuple[int, Counter[str]]:
    """How many files the folder holds, and how many of them stand in a library or environment folder."""
    total = 0
    libraries: Counter[str] = Counter()
    try:
        for path in folder.rglob("*"):
            if total >= MAX_WALK:
                break
            if not path.is_file():
                continue
            total += 1
            inside = LIBRARY_FOLDERS & set(path.relative_to(folder).parts[:-1])
            if inside:
                libraries[sorted(inside)[0]] += 1
    except OSError:
        pass
    return total, libraries


def _knowledge_sizes(page: Page, root: Path, home: Path) -> bool:
    found = False
    for store in sorted((home / "memory" / "scopes").glob("*/knowledge")):
        topics = len(list((store / "topics").glob("*.md"))) if (store / "topics").is_dir() else 0
        structure = store / "structure.json"
        size = structure.stat().st_size // 1024 if structure.is_file() else 0
        page.lines.append(
            f"knowledge of {store.parent.name[:40]}: {topics} topics, structure.json {size:,} KB"
        )
        found = True
    logs = [p for p in (root / ".forge").rglob("events.jsonl")] if (root / ".forge").is_dir() else []
    if logs:
        page.lines.append(
            f"event logs of the project: {len(logs)}, {sum(p.stat().st_size for p in logs) // 1024:,} KB"
        )
    return found


def delivery_page(conversations: list[Conversation], root: Path, home: Path | None = None) -> Page:
    """WF2, KP8, KP7 and KP0: temporary changes and the leftover review, the delivery folder, the index."""
    home = home or forge_home()
    page = Page("DELIVERY, TEMPORARY CHANGES, INDEX")
    calls = [call for c in conversations for call in c.calls]
    events = [e for c in conversations for e in c.events]

    try:
        stored = json.loads((root / ".forge" / "temporary_edits.json").read_text(encoding="utf-8"))
        entries = [e for e in stored.get("entries", []) if isinstance(e, dict)]
    except (OSError, ValueError, AttributeError):
        entries = []
    kinds = Counter(f"{e.get('kind')} {e.get('state')}" for e in entries)
    page.lines.append(f"changes marked temporary: {len(entries)} {dict(kinds) if kinds else ''}".rstrip())
    for entry in entries[-3:]:
        page.lines.append(f"   #{entry.get('id')} {entry.get('kind')} {Path(str(entry.get('path'))).name}")
    reminders = _notices(events, "temporary_changes")
    leftovers = _notices(events, "leftover_review")
    page.lines.append(
        f"reminders about temporary changes: {len(reminders)}; the leftover review named something: "
        f"{len(leftovers)}x"
    )
    for event in leftovers[-2:]:
        page.lines.append(f"   {' '.join(str(event.payload.get('text', '')).split())[:90]}")
    edits = [c for c in calls if c.name in EDITING]
    page.verdicts.append(
        Verdict("WF2", "NOT RUN", "no edit in any conversation yet; do step 5")
        if not edits
        else Verdict(
            "WF2",
            "CHECK" if leftovers else "PASS",
            f"{len(edits)} edits, {len(entries)} marked temporary, review spoke {len(leftovers)}x"
            + (": judge what it named" if leftovers else ""),
        )
    )

    output = root / "output"
    total, libraries = _files_under(output) if output.is_dir() else (0, Counter())
    page.lines.append(
        f"delivery folder: {total}{'+' if total >= MAX_WALK else ''} files; in library folders: "
        f"{sum(libraries.values())} {dict(libraries) if libraries else ''}".rstrip()
    )
    refused = sum(1 for c in calls if c.name == "run_command" and "--target" in c.text() and not c.ok)
    page.lines.append(f"   pip install --target refused: {refused}x")
    page.verdicts.append(
        Verdict("KP8", "NOT RUN", "the project has no delivery folder with files yet")
        if not total
        else Verdict("KP8", "PASS", f"{total} files delivered, none in a library folder")
        if not libraries
        else Verdict(
            "KP8", "FAIL", f"{sum(libraries.values())} delivered files are libraries: {list(libraries)}"
        )
    )

    slow: list[tuple[float, str, int, int]] = []
    seconds: list[float] = []
    for conversation in conversations:
        mine = [c for c in conversation.calls if c.name in KNOWLEDGE]
        for position, call in enumerate(mine, start=1):
            seconds.append(call.seconds)
            slow.append((call.seconds, f"{call.name} in {conversation.id}", position, len(mine)))
    if seconds:
        worst = max(slow)
        page.lines.append(
            f"knowledge tools: {len(seconds)} calls, median {statistics.median(seconds):.1f}s, slowest "
            f"{worst[0]:.1f}s ({worst[1]}, call {worst[2]} of {worst[3]})"
        )
        over = sum(1 for value in seconds if value > SLOW_INDEX_S)
        page.verdicts.append(
            Verdict("KP7", "PASS", f"{len(seconds)} calls, slowest {worst[0]:.1f}s")
            if not over
            else Verdict("KP7", "CHECK", f"{over} of {len(seconds)} calls took over {SLOW_INDEX_S:.0f}s")
        )
    else:
        page.lines.append("knowledge tools: no call in the logs")
        page.verdicts.append(Verdict("KP7", "NOT RUN", "no code_map or knowledge call yet; do step 6"))
    sizes = _knowledge_sizes(page, root, home)
    page.verdicts.append(
        Verdict("KP0", "PASS", "the sizes and the seconds are on this page")
        if sizes and seconds
        else Verdict("KP0", "NOT RUN", "no stored knowledge or no knowledge call yet; do step 6")
    )
    return page
