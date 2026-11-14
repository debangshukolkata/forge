"""`forge laptop report`: the facts from the conversations and the field log that close the laptop items (D-615).

Every function reads what DebCraft already wrote (the event logs of the project's conversations, the field log, the
run notes) and returns a `Page` with the facts and a verdict per item. Names, counts, seconds and the first words
of a card or an error only: no token, no key, no statement with a value, no file content.
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from forge.config import forge_home
from forge.engine.laptop_pages import Page, Verdict, report_folder
from forge.engine.log_summary import _first_word_section, knowledge_section
from forge.protocol.events import Event, EventType, load_event_log
from forge.toolkit import field_log

SEARCHING = {
    "code_map",
    "grep",
    "glob",
    "list_dir",
    "read_file",
    "code_outline",
    "find_definition",
    "find_references",
    "list_symbols",
    "knowledge_search",
    "db_schema",
    "db_query",
}
RUNNING = {"start_background", "http_request"}
EDITING = {"edit_file", "write_file", "multi_edit"}
CARDS = ("request_user_action", "ask_user", "request_app_secret", "request_app_keys")
SENDS_AWAY = re.compile(r"restart|bearer|paste|copy|remove the|change the line", re.IGNORECASE)
HTTP_STATUS = re.compile(r"HTTP (\d{3})")
MISSING_NAME = re.compile(r"""relation ["']?([\w.]+)["']? does not exist""")
SLOW_OPEN_S = 5.0


@dataclass
class Call:
    index: int
    name: str
    arguments: Any
    ok: bool | None
    summary: str
    preview: str

    def text(self) -> str:
        return (
            json.dumps(self.arguments, default=str) if not isinstance(self.arguments, str) else self.arguments
        )

    def argument(self, key: str) -> str:
        return str(self.arguments.get(key, "")) if isinstance(self.arguments, dict) else ""

    def status(self) -> int | None:
        found = HTTP_STATUS.search(self.preview)
        return int(found.group(1)) if found else None


@dataclass
class Conversation:
    id: str
    events: list[Event]
    calls: list[Call]


def conversation_logs(root: Path) -> list[tuple[str, Path]]:
    """The conversations of a project, oldest first (by when each log was last written)."""
    base = root / ".forge" / "conversations"
    found = [
        (folder.name, folder / "events.jsonl")
        for folder in base.glob("c*")
        if (folder / "events.jsonl").is_file()
    ]
    if not found and (root / ".forge" / "transcripts" / "events.jsonl").is_file():
        found = [("c1", root / ".forge" / "transcripts" / "events.jsonl")]
    return sorted(found, key=lambda item: item[1].stat().st_mtime)


def _calls(events: list[Event]) -> list[Call]:
    started: dict[str, tuple[int, Event]] = {}
    calls: list[Call] = []
    for position, event in enumerate(events):
        payload = event.payload
        if event.type == EventType.TOOL_CALL_STARTED:
            started[str(payload.get("id"))] = (position, event)
        elif event.type == EventType.TOOL_CALL_FINISHED:
            begin = started.get(str(payload.get("id")))
            arguments = begin[1].payload.get("arguments") if begin else None
            calls.append(
                Call(
                    begin[0] if begin else position,
                    str(payload.get("name")),
                    arguments,
                    bool(payload.get("ok")),
                    str(payload.get("summary", "")),
                    str(payload.get("preview", "")),
                )
            )
    return sorted(calls, key=lambda call: call.index)


def load_conversations(root: Path) -> list[Conversation]:
    loaded = []
    for name, path in conversation_logs(root):
        try:
            events = load_event_log(path)
        except (OSError, ValueError):
            continue
        loaded.append(Conversation(name, events, _calls(events)))
    return loaded


def _latest(conversations: list[Conversation], names: set[str], ok_only: bool = False) -> Conversation | None:
    for conversation in reversed(conversations):
        if any(call.name in names and (call.ok or not ok_only) for call in conversation.calls):
            return conversation
    return None


def _path_of(call: Call) -> str:
    """`METHOD /path` of an http_request, from its summary (`GET http://host:port/path`)."""
    parts = call.summary.split(" ")
    method = parts[0] if parts else ""
    url = next((part for part in parts if part.startswith("http")), "")
    return f"{method} {re.sub(r'^https?://[^/]+', '', url).split('?')[0]}".strip()


def _no_conversation(page: Page, items: list[str]) -> Page:
    page.lines.append("No conversation with the needed tool calls was found in this project.")
    page.verdicts += [
        Verdict(item, "NOT RUN", "no such conversation yet; do the step first") for item in items
    ]
    return page


# --- the items ---------------------------------------------------------------------------------------------


def tokens_page(conversations: list[Conversation], home: Path | None = None, with_cards: bool = True) -> Page:
    """TK5 (sign-in by itself, the token's lifetime) and RS11 (the token and Infisical cards, when `with_cards`)."""
    from forge.toolkit.app_logins import TokenStore, load_logins

    home = home or forge_home()
    page = Page("SIGN-IN AND TOKEN CARDS")
    records = field_log.read(("sign_in",), home)
    try:
        logins = load_logins(home)
    except Exception as error:  # a broken app_logins.yaml is itself the fact
        logins = {}
        page.lines.append(f"app_logins.yaml PROBLEM: {str(error)[:90]}")
    store = TokenStore(home)
    missing: list[str] = []
    for login in logins.values():
        mine = [r for r in records if r.get("env") == login.name]
        paths = Counter(str(r.get("path")) for r in mine)
        span = store.lifetime(login.token_name)
        life = f"{span[0] // 60} min ({'own exp claim' if span[1] else 'guessed'})" if span else "unknown"
        page.lines.append(
            f"{login.name}: sign-ins {len(mine)} " + ", ".join(f"{k} x{n}" for k, n in paths.items())
        )
        for record in mine[-3:]:
            page.lines.append(
                f"   {str(record.get('ts', ''))[5:16]} {record.get('path')} ok={record.get('ok')} "
                f"{record.get('seconds')}s left {record.get('minutes_left')} min {str(record.get('detail', ''))[:40]}"
            )
        page.lines.append(
            f"   token lasts {life}; left now {(store.remaining(login.token_name) or 0) // 60} min"
        )
        window_at = next((i for i, r in enumerate(mine) if r.get("path") == "window" and r.get("ok")), None)
        silent_after = window_at is not None and any(
            r.get("path") in ("stored", "silent") and r.get("ok") for r in mine[window_at + 1 :]
        )
        if not any(r.get("ok") for r in mine):
            missing.append(f"{login.name}: no successful sign-in logged")
        elif window_at is not None and not silent_after:
            missing.append(f"{login.name}: window once, no later sign-in without a window yet")
    tk5 = (
        Verdict("TK5", "NOT RUN", "no environment in app_logins.yaml")
        if not logins
        else Verdict("TK5", "PASS", "every environment signed in; a later one needed no window")
        if not missing
        else Verdict("TK5", "CHECK", "; ".join(missing)[:150])
    )
    page.verdicts.append(tk5)
    if not with_cards:
        return page

    conversation = _latest(conversations, {"http_request"})
    page.lines.append("")
    if conversation is None:
        page.lines.append("RS11: no conversation with an http_request yet.")
        page.verdicts.append(Verdict("RS11", "NOT RUN", "no http_request in any conversation"))
        return page
    cards = [c for c in conversation.calls if c.name in CARDS]
    sending = [c for c in cards if SENDS_AWAY.search(c.text()) and c.name != "request_app_secret"]
    secret_cards = [c for c in cards if c.name == "request_app_secret"]
    statuses = [c.status() for c in conversation.calls if c.name == "http_request"]
    page.lines.append(f"RS11 in {conversation.id}: cards {len(cards)} (asks for names {len(secret_cards)})")
    page.lines.append("   http_request statuses: " + (" ".join(str(s) for s in statuses[:12]) or "none"))
    for card in secret_cards[:2]:
        page.lines.append(f"   names asked: {card.argument('names')[:80]} ok={card.ok}")
    for card in sending[:4]:
        page.lines.append(f"   SENDS YOU SOMEWHERE: {card.name}: {card.text()[:80]}")
    worked = any(s is not None and s < 400 for s in statuses)
    page.verdicts.append(
        Verdict("RS11", "PASS", f"API answered, {len(secret_cards)} names card, nothing sends you away")
        if worked and not sending and len(secret_cards) <= 1
        else Verdict(
            "RS11",
            "CHECK",
            f"worked={worked} sending-away cards={len(sending)} names cards={len(secret_cards)}",
        )
    )
    return page


def second_run_page(conversations: list[Conversation], root: Path) -> Page:
    """RN2: the second conversation repeats the first one's run from the notes, without searching."""
    page = Page("SECOND RUN FROM THE NOTES")
    ran = [c for c in conversations if any(call.name in RUNNING and call.ok for call in c.calls)]
    notes_path = root / ".forge" / "run_notes.json"
    try:
        notes = json.loads(notes_path.read_text(encoding="utf-8"))
        page.lines.append(
            f"run_notes.json: {len(notes.get('starts', []))} starts "
            f"{[s.get('name') for s in notes.get('starts', [])][:3]}, {len(notes.get('calls', []))} calls "
            f"{[c.get('method', '') + ' ' + str(c.get('url', ''))[-40:] for c in notes.get('calls', [])][:2]}"
        )
    except (OSError, ValueError):
        page.lines.append("run_notes.json: none")
    if len(ran) < 2:
        page.lines.append(f"conversations that ran the application: {len(ran)} (two are needed)")
        page.verdicts.append(Verdict("RN2", "NOT RUN", f"{len(ran)} conversation(s) ran it; do step 4 twice"))
        return page
    first, second = ran[0], ran[1]
    rows = []
    for conversation in (first, second):
        first_run = next((c.index for c in conversation.calls if c.name in RUNNING), 10**9)
        before = [c for c in conversation.calls if c.index < first_run]
        search = Counter(c.name for c in before if c.name in SEARCHING)
        http = [c for c in conversation.calls if c.name == "http_request"]
        rows.append((conversation, sum(search.values()), search, http))
        page.lines.append(
            f"{conversation.id}: searched {sum(search.values())}x before the first run "
            f"{dict(search.most_common(3))}; starts {sum(1 for c in conversation.calls if c.name == 'start_background')}"
            f", http_request {len(http)} (ok {sum(1 for c in http if c.ok)})"
        )
    paths_first = {_path_of(c) for c in rows[0][3] if c.ok}
    paths_second = {_path_of(c) for c in rows[1][3] if c.ok}
    same = sorted(paths_first & paths_second)
    page.lines.append(f"same call repeated: {same[:2] or 'NO'}")
    searched = rows[1][1]
    page.verdicts.append(
        Verdict("RN2", "PASS", f"{second.id} repeated {same[0]} after {searched} searches")
        if same and searched <= 6
        else Verdict("RN2", "CHECK", f"second run searched {searched}x; same call: {bool(same)}")
    )
    return page


def requirement_page(conversations: list[Conversation]) -> Page:
    """RS7 (a real requirement) and DB2 (does it guess names)."""
    page = Page("THE REQUIREMENT ON THE REAL AGENT")
    conversation = _latest(conversations, EDITING)
    if conversation is None:
        return _no_conversation(page, ["RS7", "DB2"])
    calls = conversation.calls
    edits = [c for c in calls if c.name in EDITING]
    first_edit, last_edit = edits[0].index, edits[-1].index
    http = [c for c in calls if c.name == "http_request"]
    before = [c.status() for c in http if c.index < first_edit]
    after = [c.status() for c in http if c.index > last_edit]
    files = Counter(c.argument("path") or c.argument("file_path") for c in edits)
    page.lines += [
        f"{conversation.id}: tool calls {len(calls)}, edits {len(edits)} in {len(files)} files",
        "files: " + ", ".join(Path(name).name for name in list(files)[:6] if name),
        f"http_request before the first edit: {before or 'none'}",
        f"http_request after the last edit:   {after or 'none'}",
        f"database tools: copy {sum(1 for c in calls if c.name == 'db_copy_table')}, scratch "
        f"{sum(1 for c in calls if c.name == 'use_scratch_database')}, dev {sum(1 for c in calls if c.name == 'use_dev_database')}"
        f", dev write {sum(1 for c in calls if c.name == 'dev_db_write')}",
    ]
    last_message = next(
        (
            e.payload.get("text", "")
            for e in reversed(conversation.events)
            if e.type == EventType.MESSAGE_DONE
        ),
        "",
    )
    page.lines.append("last words: " + " ".join(str(last_message).split())[:160])
    proof = any(s is not None and s < 400 for s in after)
    page.verdicts.append(
        Verdict("RS7", "PASS", "the API answered before and after the change")
        if proof and any(s is not None for s in before)
        else Verdict("RS7", "CHECK", f"before {before[:3]} after {after[:3]}: judge from the last words")
    )

    guessed = [
        c for c in calls if c.name == "db_query" and not c.ok and "does not exist" in c.preview.lower()
    ]
    answered = 0
    for call in guessed:
        later = [c.name for c in calls if call.index < c.index <= call.index + 6]
        answered += bool({"db_schema", "code_map"} & set(later))
    names = [found.group(1) for c in guessed for found in [MISSING_NAME.search(c.preview)] if found]
    page.lines.append(f"db_query on a missing name: {len(guessed)} {names[:4]}; looked up after: {answered}")
    page.verdicts.append(
        Verdict(
            "DB2", "PASS", "no guessed name" if not guessed else f"{answered}/{len(guessed)} looked up after"
        )
        if answered == len(guessed)
        else Verdict(
            "DB2", "CHECK", f"{len(guessed) - answered} missing names were not looked up: {names[:3]}"
        )
    )
    return page


def dev_database_page(conversations: list[Conversation], home: Path | None = None) -> Page:
    """What the Development DB tools and the relay did in real use (DV8, DV9, DV10)."""
    home = home or forge_home()
    page = Page("DEVELOPMENT DB IN REAL USE")
    events = [e for c in conversations for e in c.events]
    calls = [call for c in conversations for call in c.calls]
    held = [
        e.payload
        for e in events
        if e.type == EventType.NOTICE and e.payload.get("kind") == "dev_settings_held"
    ]
    page.lines.append(
        "held-back settings: "
        + (re.sub(r"\s+", " ", str(held[-1].get("text", "")))[:110] if held else "none found")
    )
    cards = [e for e in events if e.type == EventType.QUESTION_ASKED and e.payload.get("danger")]
    answers = {e.payload.get("id"): e.payload for e in events if e.type == EventType.QUESTION_ANSWERED}
    approved = sum(
        1
        for c in cards
        if answers.get(c.payload.get("id"), {}).get("choice") == c.payload["options"][0]["label"]
    )
    page.lines.append(
        f"red cards: {len(cards)} shown, {approved} approved, {len(cards) - approved} not approved"
    )
    for card in cards[-3:]:
        page.lines.append(f"   {str(card.payload.get('question', ''))[:92]}")
    writes = [c for c in calls if c.name == "dev_db_write"]
    page.lines.append(f"dev_db_write: {len(writes)} calls, {sum(1 for c in writes if c.ok)} committed")
    for call in [c for c in writes if not c.ok][:2]:
        page.lines.append(f"   failed: {' '.join(call.preview.split())[:92]}")
    page.lines.append(f"use_dev_database: {sum(1 for c in calls if c.name == 'use_dev_database')} calls")
    activity = [
        e.payload for e in events if e.type == EventType.NOTICE and e.payload.get("kind") == "dev_db_activity"
    ]
    page.lines.append(f"relay reports to you after a turn: {len(activity)}")
    for payload in activity[-2:]:
        page.lines.append("   " + " | ".join(str(payload.get("text", "")).splitlines()[:3])[:94])
    relay = field_log.read(("relay_start", "relay_stop", "relay_error", "refuser_hit", "refuser_stop"), home)
    stops = [r for r in relay if r.get("kind") == "relay_stop"]
    if stops:
        stop = stops[-1]
        page.lines.append(
            f"relay (last): {stop.get('seconds')}s, {stop.get('connections')} connections, writing "
            f"{stop.get('writing_statements')}, refused {stop.get('refused_statements')}, rows {stop.get('rows')}"
        )
        page.lines.append(f"   messages {stop.get('messages')} errors {stop.get('errors') or 'none'}")
    for record in [r for r in relay if r.get("kind") == "relay_error"][-2:]:
        page.lines.append(f"   relay error: {record.get('where')} {record.get('type')}: {record.get('text')}")
    hits = [r for r in relay if r.get("kind") == "refuser_hit"]
    page.lines.append(
        f"copy tried a held-back setting: {len(hits)}x" + (f" {hits[-1].get('settings')}" if hits else "")
    )
    page.verdicts.append(
        Verdict("DV10", "PASS", f"held back: {bool(held)}; the copy hit the refusal {len(hits)}x")
        if held
        else Verdict("DV10", "NOT RUN", "no conversation yet")
        if not events
        else Verdict(
            "DV10", "CHECK", "no held-back notice: no setting of the copy points at the Development DB?"
        )
    )
    used = stops and not [r for r in relay if r.get("kind") == "relay_error"]
    page.verdicts.append(
        Verdict("DV8", "PASS", f"relay ran {len(stops)}x without an error in real use")
        if used
        else Verdict(
            "DV8", "NOT RUN", "the relay was not used in a real session (the driver check is on its own page)"
        )
    )
    return page


def speed_page(conversations: list[Conversation]) -> Page:
    """RS19 (opening), HW6 (first word by size), KL6 (knowledge layer), RS15 (hand-off cards)."""
    page = Page("SPEED, KNOWLEDGE AND HAND-OFF CARDS")
    events = [e for c in conversations for e in c.events]
    timings = [e.payload for e in events if e.type == EventType.SESSION_TIMING]
    opens = [float(t.get("open_s", 0)) for t in timings]
    maps = [float(t["map_s"]) for t in timings if t.get("map_s") is not None]
    page.lines.append(
        f"opening the project: {len(opens)}x, median {statistics.median(opens):.1f}s, slowest {max(opens):.1f}s"
        if opens
        else "opening the project: no timing in the logs"
    )
    if maps:
        page.lines.append(
            f"reading the repository map: median {statistics.median(maps):.1f}s, slowest {max(maps):.1f}s"
        )
    page.verdicts.append(
        Verdict("RS19", "NOT RUN", "no open time logged")
        if not opens
        else Verdict(
            "RS19",
            "PASS" if max(opens) <= SLOW_OPEN_S else "CHECK",
            f"opens {len(opens)}x, slowest {max(opens):.1f}s",
        )
    )
    llm = [e.payload for e in events if e.type == EventType.LLM_CALL]
    first_word = [line for line in _first_word_section(llm) if line.strip() and not line.startswith("##")]
    page.lines += first_word[:7]
    page.verdicts.append(
        Verdict("HW6", "NOT RUN", "no model call in the logs")
        if not llm
        else Verdict("HW6", "PASS", f"{len(llm)} model calls in the table")
        if len(llm) >= 10
        else Verdict("HW6", "CHECK", f"only {len(llm)} model calls: use DebCraft longer")
    )
    knowledge = [line.strip("- ") for line in knowledge_section(events) if line.startswith("- ")]
    page.lines += knowledge[:5]
    tools = Counter(c.name for conv in conversations for c in conv.calls)
    used = tools["knowledge_search"] + tools["code_map"]
    page.verdicts.append(
        Verdict(
            "KL6",
            "PASS",
            f"code_map {tools['code_map']}x, knowledge_search {tools['knowledge_search']}x, write {tools['knowledge_write']}x",
        )
        if used
        else Verdict("KL6", "NOT RUN", "no code_map or knowledge_search call yet; do step 6")
    )
    handoffs = [c for conv in conversations for c in conv.calls if c.name == "request_user_action"]
    held = [
        e.payload for e in events if e.type == EventType.NOTICE and e.payload.get("kind") == "handoff_review"
    ]
    page.lines.append(
        f"hand-off cards that reached you: {len(handoffs)}; held back by the review: {len(held)}"
    )
    for number, call in enumerate(handoffs[-6:], start=1):
        page.lines.append(f"   {number}. {call.argument('title')[:84]}")
    for payload in held[-3:]:
        page.lines.append(f"   held back: {str(payload.get('text', ''))[:84]}")
    page.verdicts.append(
        Verdict(
            "RS15", "CHECK", f"{len(handoffs)} cards reached you, {len(held)} held back: judge each title"
        )
        if handoffs or held
        else Verdict("RS15", "NOT RUN", "no hand-off card in any conversation")
    )
    return page


def live_tests_page(home: Path | None = None) -> Page:
    """TR6: the result of `forge laptop live`."""
    page = Page("LIVE TESTS ON THIS LAPTOP")
    path = report_folder(home) / "live_tests.json"
    try:
        results = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        page.lines.append("forge laptop live has not been run.")
        page.verdicts.append(Verdict("TR6", "NOT RUN", "run: forge laptop live"))
        return page
    for entry in results:
        page.lines.append(
            f"{entry['file']}: passed {entry['passed']}, failed {entry['failed']}, skipped {entry['skipped']}, {entry['seconds']}s"
        )
        page.lines += [f"   {line}" for line in entry.get("notes", [])[:4]]
    tool_search = next((e for e in results if e["file"] == "test_live_tool_search.py"), None)
    page.verdicts.append(
        Verdict("TR6", "NOT RUN", "test_live_tool_search.py was not run")
        if tool_search is None
        else Verdict(
            "TR6",
            "PASS" if tool_search["failed"] == 0 and tool_search["passed"] else "CHECK",
            f"passed {tool_search['passed']}, failed {tool_search['failed']}, skipped {tool_search['skipped']}",
        )
    )
    return page
