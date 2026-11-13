"""`forge facts`: the facts that close the open items, on three short screens to photograph (D-607).

Page 1 is the setup (the sign-in and tunnel files, the token states without their values, the tunnel port, what is
installed); page 2 the numbers of the latest conversation (how long opening took, failures, repeated calls, the time to
the first word, calls to the sign-in and the application); page 3 the cards DebCraft showed the user and the notices.
Names, counts, seconds and the first words of a card only: no token, no key, no file content. Everything passes the
redactor once more before it is printed."""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from forge.config import forge_home
from forge.engine.log_summary import _failure_reason, _first_word_section, _median
from forge.errors import ConfigError
from forge.protocol.events import Event, EventType, load_event_log
from forge.safety.redact import default_redactor
from forge.workspace.conversations import conversation_file

CARD_TOOLS = ("request_user_action", "ask_user", "request_app_secret", "request_app_keys")
FIRST_PAGE = "Photograph each screen; press Enter for the next one."


def newest_workspace(home: Path | None = None) -> Path | None:
    """The recent project whose transcript was written last."""
    try:
        recent = json.loads(((home or forge_home()) / "recent_workspaces.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    best: tuple[float, Path] | None = None
    for entry in recent if isinstance(recent, list) else []:
        root = Path(str(entry.get("path", ""))) if isinstance(entry, dict) else None
        if root is None:
            continue
        log = conversation_file(root, "events.jsonl")
        if log.is_file() and (best is None or log.stat().st_mtime > best[0]):
            best = (log.stat().st_mtime, root)
    return best[1] if best else None


def _yes(value: bool) -> str:
    return "yes" if value else "NO"


def setup_page(home: Path | None = None) -> list[str]:
    from forge.db.tunnel import LOG_NAME, TUNNELS_FILE, load_tunnels, port_open
    from forge.toolkit.app_logins import LOGINS_FILE, load_logins
    from forge.tools.app_login import MARKER, profile_dir, token_status

    home = home or forge_home()
    lines = [
        "PAGE 1 of 3: SETUP",
        f"Python {sys.version.split()[0]} | DebCraft Home: {home}",
        f"gcloud on PATH: {_yes(shutil.which('gcloud') is not None)}"
        f" | app.env: {_yes((home / 'app.env').is_file())}",
        "",
        f"{LOGINS_FILE}: {_yes((home / LOGINS_FILE).is_file())}",
    ]
    try:
        logins = load_logins(home)
    except ConfigError as error:
        logins = {}
        lines.append(f"  PROBLEM: {str(error)[:150]}")
    for login in logins.values():
        status = asyncio.run(token_status(login, home))
        steps = ", ".join(f"{step.action}" for step in login.steps)
        path = urlparse(login.check_url).path if login.check_url else "none"
        left = f", {status.minutes} min left" if status.minutes is not None else ""
        lines += [
            f"  {login.name}: {login.token_name} = {status.state.upper()}{left} {status.detail}".rstrip(),
            f"    host {login.host} | check {path} | warn {login.warn_without_token}"
            f" | signed in before: {_yes((profile_dir(login, home) / MARKER).exists())}",
            f"    steps: {steps or 'none'}",
        ]
    lines += ["", f"{TUNNELS_FILE}: {_yes((home / TUNNELS_FILE).is_file())}"]
    try:
        tunnels = load_tunnels(home)
    except ConfigError as error:
        tunnels = {}
        lines.append(f"  PROBLEM: {str(error)[:150]}")
    for spec in tunnels.values():
        lines.append(
            f"  {spec.name}: program {spec.command[0]} | port {spec.port} open now: {_yes(port_open(spec.port))}"
        )
        log = home / LOG_NAME.format(name=spec.name)
        if log.is_file():
            tail = [
                x.strip() for x in log.read_text(encoding="utf-8", errors="replace").splitlines() if x.strip()
            ]
            lines += [f"    log: {line[:110]}" for line in tail[-3:]]
    return lines


def _seconds(values: list[float]) -> str:
    return f"{len(values)} x, median {_median(values):.1f}s, slowest {max(values):.1f}s" if values else "none"


def run_page(events: list[Event]) -> list[str]:
    tools = [e.payload for e in events if e.type == EventType.TOOL_CALL_FINISHED]
    llm = [e.payload for e in events if e.type == EventType.LLM_CALL]
    opens = [float(e.payload.get("open_s", 0)) for e in events if e.type == EventType.SESSION_TIMING]
    maps = [
        float(e.payload["map_s"])
        for e in events
        if e.type == EventType.SESSION_TIMING and e.payload.get("map_s") is not None
    ]
    failed = [t for t in tools if not t.get("ok")]
    repeats = Counter((t.get("name"), t.get("summary", "")) for t in tools)
    names = Counter(str(t.get("name")) for t in tools)
    queries = [t for t in tools if t.get("name") == "db_query"]
    guessed = [
        t for t in queries if not t.get("ok") and "does not exist" in str(t.get("preview", "")).lower()
    ]
    lines = [
        "PAGE 2 of 3: THE LATEST CONVERSATION",
        f"events {len(events)} | model calls {len(llm)} | tool calls {len(tools)} | failed {len(failed)}"
        f" | repeated {sum(n - 1 for n in repeats.values() if n > 1)}",
        f"opening the project: {_seconds(opens)} | repository map: {_seconds(maps)}",
        f"db_query: {len(queries)} calls, {len(failed_of(queries))} failed, {len(guessed)} on a name that does not exist",
    ]
    top_failures = Counter(
        (str(t.get("name")), " ".join(_failure_reason(t.get("preview", "")).split())[:60]) for t in failed
    ).most_common(4)
    lines += [f"  failed x{n} {name}: {reason}" for (name, reason), n in top_failures]
    for tool_name in (
        "tool_search",
        "app_login",
        "app_token_status",
        "http_request",
        "code_map",
        "conversation_recall",
    ):
        if names[tool_name]:
            bad = sum(1 for t in tools if t.get("name") == tool_name and not t.get("ok"))
            lines.append(f"{tool_name}: {names[tool_name]} calls, {bad} failed")
    hosts = Counter(
        urlparse(str(t.get("summary", "")).split(" ")[-1]).hostname or "local/other"
        for t in tools
        if t.get("name") == "http_request"
    )
    if hosts:
        lines.append("http_request hosts: " + ", ".join(f"{host} x{n}" for host, n in hosts.most_common(4)))
    lines += [line for line in _first_word_section(llm) if line.strip() and not line.startswith("##")]
    return lines


def failed_of(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [t for t in tools if not t.get("ok")]


def cards_page(events: list[Event]) -> list[str]:
    lines = ["PAGE 3 of 3: CARDS AND NOTICES (first words only)"]
    cards = [
        e.payload
        for e in events
        if e.type == EventType.TOOL_CALL_FINISHED and e.payload.get("name") in CARD_TOOLS
    ]
    lines.append(f"cards shown to the user: {len(cards)}")
    for card in cards[-8:]:
        lines.append(f"  {card.get('name')}: {str(card.get('summary', ''))[:100]}")
    kinds = Counter(str(e.payload.get("kind", "?")) for e in events if e.type == EventType.NOTICE)
    lines.append("notices: " + (", ".join(f"{k} x{n}" for k, n in kinds.most_common(8)) or "none"))
    for event in events:
        if event.type == EventType.NOTICE and event.payload.get("kind") in (
            "handoff_review",
            "token_warning",
        ):
            lines.append(f"  {event.payload['kind']}: {str(event.payload.get('text', ''))[:110]}")
    errors = [str(e.payload.get("message", ""))[:110] for e in events if e.type == EventType.ERROR]
    lines.append(f"errors: {len(errors)}")
    lines += [f"  {message}" for message in errors[-4:]]
    return lines


def build_pages(
    workspace: Path | None, conversation: str | None = None, home: Path | None = None
) -> list[str]:
    pages = ["\n".join(setup_page(home))]
    log = conversation_file(workspace, "events.jsonl", conversation) if workspace else None
    if log is None or not log.is_file():
        pages.append("PAGE 2 of 3: no conversation found. Run forge facts --workspace <project folder>.")
        pages.append("PAGE 3 of 3: no conversation found.")
    else:
        events = load_event_log(log)
        pages.append(f"{workspace}\n" + "\n".join(run_page(events)))
        pages.append("\n".join(cards_page(events)))
    return [default_redactor.redact(page) for page in pages]


def show(
    workspace: Path | None,
    conversation: str | None = None,
    pause: bool = True,
    write: Callable[[str], None] = print,
    wait: Callable[[str], str] = input,
) -> int:
    workspace = workspace or newest_workspace()
    pages = build_pages(workspace, conversation)
    for number, page in enumerate(pages):
        write(("\n" if number else "") + page)
        if pause and number < len(pages) - 1:
            wait(f"\n[{FIRST_PAGE}]")
    return 0
