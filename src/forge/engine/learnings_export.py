"""`/learnings export`: candidates for general lessons, for the user to review (D-650).

Facts about a repository stay where they are. What could improve DebCraft itself is collected from what happened:
feedback the user gave, sentences in which the user corrected it, calls that failed again and again, checks that had to
send the model back, and notes that had to be corrected. It only writes a file on this machine. Names that could
belong to the user's company are replaced, which cannot be complete: the user reads the file before anyone else does."""

from __future__ import annotations

import getpass
import json
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from forge.config import forge_home
from forge.errors import ConfigError
from forge.home_layout import data_path
from forge.memory.store import STATE_MEMORY, Memory, MemoryStore
from forge.safety.redact import default_redactor
from forge.toolkit.app_logins import load_logins
from forge.tools.registry import default_tools

PRIVATE_TERMS = "private_terms.txt"  # the user's own list, one word per line, in DebCraft Home
MAX_TEXT = 400
MAX_EACH = 40
REPEATED = 3  # a failure this often is a pattern
WANTED = ("user_message", "tool_call_finished", "notice")
# what the loop tells the model before it lets a turn end, and what the user can read as a lesson
CHECKS = {
    "proof_call": "asked for the API call to be run again after a code change",
    "handover_check": "a curl, a failing call or made-up values had not been proven or named",
    "todo_continue": "stopped with open to-do items",
    "question_to_options": "asked the user in plain text instead of with options",
    "leftover_review": "changes made to investigate were still there",
    "temporary_changes": "temporary changes were still in the copy",
    "knowledge_check": "a repository note in use was doubtful",
    "compaction_fallback": "the model's summary of the conversation was incomplete",
    "fallback": "switched to another model",
}
CORRECTION = re.compile(
    r"\b(?:that(?:'s| is) (?:wrong|not)|this is (?:wrong|not)|wrong|incorrect|you should(?: have| not)?|you did(?:n't| not)|"
    r"don't|do not|never|instead|i (?:told|asked|said)|already (?:told|said|gave)|again|why did you|stop)\b",
    re.IGNORECASE,
)
COMMON_LABELS = {
    "www", "com", "org", "net", "app", "apps", "api", "dev", "sit", "uat", "test", "prod", "nonprod", "local",
    "cloud", "internal", "login", "auth", "service", "services", "example",
}  # fmt: skip
COMMON_WORDS = COMMON_LABELS | {
    "src", "repo", "backend", "frontend", "main", "work", "project", "projects", "code", "data", "web", "tests",
    "users", "user", "home", "desktop", "documents", "agent", "server", "client", "tool", "tools",
    "development", "localdevelopment", "forgeprojects", "python", "flow",
}  # fmt: skip
HEAD = (
    "READ THIS BEFORE YOU SEND IT TO ANYONE. Names, addresses and paths were replaced automatically, which cannot be",
    "complete: delete every line that says something about your company or its systems. Nothing was sent anywhere.",
    f"More words to hide: one per line in {PRIVATE_TERMS} in DebCraft Home, then run /learnings export again.",
)
FULL_HEAD = (
    "Full export: names, addresses and everything DebCraft saved are in it; only keys, tokens and passwords are masked.",
    "Masking cannot be complete: look for anything that must not leave this machine before you send it.",
)
URL = re.compile(r"\b(?:https?|postgresql|postgres|wss?|ftp)(?:\+\w+)?://[^\s'\"`)>\]]+", re.IGNORECASE)
EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
HOST = re.compile(r"\b(?:[a-z0-9-]+\.){2,}[a-z]{2,}\b", re.IGNORECASE)
ADDRESS = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
WINDOWS_PATH = re.compile(r"[A-Za-z]:[\\/][^\s'\"`|<>]*|\\\\[^\s'\"`|<>]+")
PATH = re.compile(r"(?<![\w<])(?:\.{0,2}/)?(?:[\w.{}<>-]+/)+[\w.{}<>-]*")
FILE = re.compile(
    r"\b[\w-]+\.(?:py|ts|tsx|js|jsx|java|cs|go|sql|md|json|ya?ml|toml|html|css|txt|csv|xlsx|docx|pptx|pdf|mp4)\b",
    re.I,
)
LONG_ID = re.compile(
    r"\b[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\b|\b[A-Za-z0-9_-]{32,}\b|\b\d{4,}\b"
)
IDENTIFIER = re.compile(
    r"\b(?:[A-Za-z0-9]+_[A-Za-z0-9_]+|[a-z]+[A-Z]\w*|(?:[A-Z][a-z0-9]+){2,}|[A-Z]{2,}[A-Z0-9_]*_[A-Z0-9_]+)\b"
)
QUOTED = re.compile(r"(['\"])(?:(?!\1).){3,}\1|`[^`]{3,}`")


def private_terms(home: Path, projects: list[dict[str, Any]]) -> set[str]:
    """Words that could name the user, the company or its systems: from the sign-in hosts, the projects, the machine and
    the user's own list."""
    terms: set[str] = {getpass.getuser().lower()}
    try:
        for login in load_logins(home).values():
            terms |= {label.lower() for label in re.split(r"[.-]", login.host)}
    except ConfigError:
        pass
    for entry in projects:
        for key in ("name", "repo", "path"):
            terms |= {word.lower() for word in re.split(r"[^A-Za-z0-9]+", str(entry.get(key, "")))}
    terms = {term for term in terms if len(term) >= 4 and term not in COMMON_WORDS and not term.isdigit()}
    try:
        own = (home / PRIVATE_TERMS).read_text(encoding="utf-8-sig").splitlines()
        terms |= {line.strip().lower() for line in own if len(line.strip()) >= 2 and not line.startswith("#")}
    except OSError:
        pass
    return terms


def masker(home: Path, projects: list[dict[str, Any]]) -> Callable[[str], str]:
    terms = sorted(private_terms(home, projects), key=len, reverse=True)
    named = re.compile("|".join(re.escape(term) for term in terms), re.IGNORECASE) if terms else None
    ours = {tool.name for tool in default_tools()}

    def mask(text: str) -> str:
        text = default_redactor.redact(text)
        text = URL.sub(lambda m: "<local address>" if _is_local(m.group()) else "<address>", text)
        for pattern, word in (
            (EMAIL, "<email>"),
            (WINDOWS_PATH, "<path>"),
            (LONG_ID, "<id>"),
            (HOST, "<host>"),
            (ADDRESS, "<address>"),
            (PATH, "<path>"),
            (FILE, "<file>"),
        ):
            text = pattern.sub(word, text)
        text = IDENTIFIER.sub(lambda m: m.group() if m.group() in ours else "<name>", text)
        if named is not None:
            text = named.sub("<private>", text)
        return " ".join(text.split())

    return mask


def _is_local(url: str) -> bool:
    return (urlparse(url).hostname or "") in ("127.0.0.1", "localhost", "::1")


def _projects(home: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(data_path(home, "recent_workspaces.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [entry for entry in data if isinstance(entry, dict)] if isinstance(data, list) else []


def _logs(project: dict[str, Any]) -> list[Path]:
    root = Path(str(project.get("path", ""))) / ".forge"
    return [*sorted((root / "conversations").glob("*/events.jsonl")), root / "transcripts" / "events.jsonl"]


def _events(path: Path) -> Iterator[tuple[str, dict[str, Any]]]:
    """(type, payload) of the kinds that matter; a log of many megabytes is read line by line."""
    try:
        with path.open(encoding="utf-8", errors="replace") as log:
            for line in log:
                if not any(kind in line[:400] for kind in WANTED):
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if (
                    isinstance(event, dict)
                    and event.get("type") in WANTED
                    and isinstance(event.get("payload"), dict)
                ):
                    yield str(event["type"]), event["payload"]
    except OSError:
        return


def corrections_in(message: str) -> list[str]:
    """The sentences of a message in which the user corrects; pasted data is left out."""
    found = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", message):
        plain = sentence.strip()
        if (
            12 <= len(plain) <= 400
            and not re.search(r"[{}\[\]<>]|^\s*(?:curl|python|\$|>)", plain)
            and CORRECTION.search(plain)
        ):
            found.append(plain)
    return found


def failure_pattern(preview: str, mask: Callable[[str], str]) -> str:
    """The first telling line of a failed call, without what changes from call to call."""
    lines = [line.strip() for line in preview.strip().splitlines() if line.strip()]
    errors = [line for line in lines if re.match(r"[\w.]*(?:Error|Exception|Refused|Denied)\b", line)]
    text = (errors or lines or ["(no text)"])[-1 if errors else 0]
    text = QUOTED.sub("<value>", text)
    return re.sub(r"\d+", "#", mask(text))[:140]


def _notes(home: Path) -> list[Memory]:
    stores = [MemoryStore(home)]
    scopes = home / "memory" / "scopes"
    for folder in sorted(scopes.iterdir()) if scopes.is_dir() else []:
        store = MemoryStore(home, "folder")
        store.folder = folder
        stores.append(store)
    return [
        note
        for store in stores
        for note in store.all()
        if note.kind == "feedback" and note.name != STATE_MEMORY
    ]


def _secrets_only(text: str) -> str:
    return " ".join(default_redactor.redact(text).split())


def build_export(home: Path, full: bool = False) -> str:
    """`full` (the user, 2026-11-24): names stay and everything learned is in it; keys and tokens are still masked."""
    projects = _projects(home)
    hidden = masker(home, projects)  # failures are grouped without their names, also in the full export
    mask = _secrets_only if full else hidden
    examples: dict[tuple[str, str], str] = {}
    failures: dict[tuple[str, str], list[int]] = defaultdict(list)
    checks: Counter[str] = Counter()
    corrections: dict[str, int] = {}
    corrected_notes: Counter[str] = Counter()
    for index, project in enumerate(projects):
        for log in _logs(project):
            for kind, payload in _events(log):
                if kind == "user_message":
                    for sentence in corrections_in(str(payload.get("text", ""))):
                        text = mask(sentence)[:MAX_TEXT]
                        corrections[text] = corrections.get(text, 0) + 1
                elif kind == "notice":
                    if str(payload.get("kind")) in CHECKS:
                        checks[str(payload["kind"])] += 1
                elif not payload.get("ok"):
                    name = str(payload.get("name"))
                    preview = str(payload.get("preview", ""))
                    key = (name, failure_pattern(preview, hidden))
                    failures[key].append(index)
                    if full:
                        examples.setdefault(key, f" (for example: {_secrets_only(preview)[:200]})")
                elif payload.get("name") == "knowledge_write":
                    metrics = payload.get("metrics")
                    if isinstance(metrics, dict) and metrics.get("outcome") == "corrected":
                        corrected_notes["notes about a repository that had to be corrected"] += 1
    out = [
        "# Candidates for general lessons",
        "",
        *(FULL_HEAD if full else HEAD),
        "",
        f"From {len(projects)} projects. Facts about your repositories and what you are working on are left out.",
        "",
    ]
    notes: dict[str, None] = {}
    for note in _notes(home):
        notes[mask(f"{note.description}: {note.text}")[:MAX_TEXT]] = None
    out += _section("Feedback you gave (saved notes)", [f"- {text}" for text in notes])
    ordered = sorted(corrections.items(), key=lambda item: -item[1])
    out += _section(
        "Sentences in which you corrected DebCraft",
        [f"- {f'{n}x ' if n > 1 else ''}{text}" for text, n in ordered],
    )
    repeated = sorted(
        ((key, where) for key, where in failures.items() if len(where) >= REPEATED),
        key=lambda item: -len(item[1]),
    )
    out += _section(
        f"Calls that failed {REPEATED} times or more in the same way",
        [
            f"- {len(where)}x in {len(set(where))} project(s), {name}: {text}{examples.get((name, text), '')}"
            for (name, text), where in repeated
        ],
    )
    out += _section(
        "Checks that had to step in",
        [f"- {count}x {kind}: {CHECKS[kind]}" for kind, count in checks.most_common()],
    )
    out += _section("Notes", [f"- {count}x {text}" for text, count in corrected_notes.items()])
    if full:
        out += _everything(home)
    return "\n".join(out).rstrip() + "\n"


def _everything(home: Path) -> list[str]:
    """Every saved note and every repository topic as it stands, secrets masked."""
    out = ["# Everything saved", ""]
    base = home / "memory"
    files = [*sorted(base.glob("*.md")), *sorted((base / "scopes").rglob("*.md"))] if base.is_dir() else []
    for file in files:
        if file.name == "MEMORY.md" or file.stem == STATE_MEMORY:
            continue
        try:
            text = default_redactor.redact(file.read_text(encoding="utf-8", errors="replace")).strip()
        except OSError:
            continue
        out += [f"## {file.relative_to(base).as_posix()}", "", text, ""]
    return out


def _section(title: str, lines: list[str]) -> list[str]:
    if not lines:
        return [f"## {title}", "", "none", ""]
    more = [f"- and {len(lines) - MAX_EACH} more"] if len(lines) > MAX_EACH else []
    return [f"## {title}", "", *lines[:MAX_EACH], *more, ""]


def write_export(home: Path | None = None, full: bool = False) -> Path:
    base = home or forge_home()
    folder = base / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"learnings-{'full-' if full else ''}{datetime.now():%Y%m%d-%H%M%S}.md"
    target.write_text(build_export(base, full), encoding="utf-8")
    return target
