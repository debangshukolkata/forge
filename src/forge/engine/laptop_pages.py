"""Pages to photograph, and the verdict of each open item (D-615).

`forge laptop` closes the items that need the user's office laptop. It prints short pages the user can photograph,
and writes the same pages as files, so a page can be opened again. A page is at most `PAGE_LINES` lines of at most
`PAGE_WIDTH` characters: it must be readable in a photograph of a screen. Every page passes the redactor before it
is printed or written. A verdict is the program's reading of the facts (PASS, CHECK, FAIL or NOT RUN); the person
who reads the photographs makes the final decision, so the facts always stand next to it.
"""

from __future__ import annotations

import contextlib
import json
import textwrap
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from forge.config import forge_home
from forge.safety.redact import default_redactor

PAGE_WIDTH = 100
PAGE_LINES = 30
REPORT_FOLDER = "laptop_report"
VERDICTS_FILE = "verdicts.json"
STATUSES = ("PASS", "CHECK", "FAIL", "NOT RUN")
# Every item that waits for the office laptop, in the order the summary lists them (TODO.md has the full text).
ITEMS = {
    "TK5": "sign in to dev and SIT by itself; how long the token lasts",
    "RN2": "a second run is repeated from the notes, without searching",
    "RS7": "a real requirement on the LangChain agent",
    "RS11": "the token and Infisical card flow asks nothing it should not",
    "RS15": "hand-off cards: needless or wrongly held back",
    "RS19": "opening a project is fast",
    "KL6": "the knowledge layer on WisdomNext",
    "DB2": "no guessing of table names; schema looked up",
    "HW6": "time to the first word by input size",
    "TR6": "live tool-search tests on the laptop's model",
    "DV8": "the relay with the drivers of the application",
    "DV9": "no triggers, rules or functions that delete",
    "DV10": "settings of the copy that point at the Development DB",
}


@dataclass
class Verdict:
    item: str
    status: str  # one of STATUSES
    line: str  # the facts in one line


@dataclass
class Page:
    title: str
    lines: list[str] = field(default_factory=list)
    verdicts: list[Verdict] = field(default_factory=list)


def _fit(line: str) -> list[str]:
    """The line in pieces of at most PAGE_WIDTH characters: a command that was cut could not be typed."""
    if len(line) <= PAGE_WIDTH:
        return [line]
    indent = "   " if line.startswith((" ", "$")) else "      "
    return textwrap.wrap(
        line, width=PAGE_WIDTH, subsequent_indent=indent, break_long_words=True, break_on_hyphens=False
    )


def paginate(pages: list[Page]) -> list[str]:
    """The text of each screen: a title, the facts, the verdicts. A page with more lines continues on the next."""
    screens: list[tuple[str, list[str]]] = []
    for page in pages:
        body = [piece for line in page.lines for piece in _fit(line)]
        tail = (
            [""] + [piece for v in page.verdicts for piece in _fit(f"{v.item:<5} {v.status:<7} {v.line}")]
            if page.verdicts
            else []
        )
        room = PAGE_LINES - 2 - len(tail)
        chunks = [body[i : i + max(8, room)] for i in range(0, max(len(body), 1), max(8, room))] or [[]]
        for number, chunk in enumerate(chunks, start=1):
            more = f" ({number}/{len(chunks)})" if len(chunks) > 1 else ""
            screens.append((page.title + more, chunk + (tail if number == len(chunks) else [])))
    total = len(screens)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    return [
        default_redactor.redact(
            f"[{number}/{total}] {title}   {stamp}\n" + "-" * 60 + "\n" + "\n".join(lines)
        )
        for number, (title, lines) in enumerate(screens, start=1)
    ]


def report_folder(home: Path | None = None) -> Path:
    return (home or forge_home()) / REPORT_FOLDER


def load_verdicts(home: Path | None = None) -> dict[str, dict[str, str]]:
    try:
        data = json.loads((report_folder(home) / VERDICTS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def save_verdicts(verdicts: list[Verdict], home: Path | None = None) -> None:
    """Keeps the latest verdict of each item, so the summary page shows every item whichever command made it."""
    stored = load_verdicts(home)
    stamp = datetime.now().isoformat(timespec="minutes")
    for verdict in verdicts:
        stored[verdict.item] = {"status": verdict.status, "line": verdict.line, "at": stamp}
    with contextlib.suppress(OSError):
        folder = report_folder(home)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / VERDICTS_FILE).write_text(json.dumps(stored, indent=1), encoding="utf-8")


def summary_page(home: Path | None = None) -> Page:
    """One screen with every open item and the latest verdict of each: the photograph that closes the list."""
    stored = load_verdicts(home)
    page = Page("SUMMARY OF THE OPEN ITEMS")
    for item, meaning in ITEMS.items():
        entry = stored.get(item)
        status = entry["status"] if entry else "NOT RUN"
        page.lines.append(f"{item:<5} {status:<7} {entry['line'] if entry else 'waiting: ' + meaning}")
    counts = {
        status: sum(1 for item in ITEMS if (stored.get(item) or {"status": "NOT RUN"})["status"] == status)
        for status in STATUSES
    }
    page.lines += ["", "  ".join(f"{status} {count}" for status, count in counts.items())]
    return page


def emit(
    pages: list[Page],
    name: str,
    pause: bool = True,
    home: Path | None = None,
    write: Callable[[str], None] = print,
    wait: Callable[[str], str] = input,
) -> Path:
    """Prints the screens one at a time and writes them under `<DebCraft Home>/laptop_report/<time>-<name>/`."""
    screens = paginate(pages)
    folder = report_folder(home) / f"{datetime.now():%Y%m%d-%H%M%S}-{name}"
    with contextlib.suppress(OSError):
        folder.mkdir(parents=True, exist_ok=True)
        for number, screen in enumerate(screens, start=1):
            (folder / f"page_{number:02d}.txt").write_text(screen + "\n", encoding="utf-8")
        (folder / "all_pages.txt").write_text(("\n\n".join(screens)) + "\n", encoding="utf-8")
    for number, screen in enumerate(screens):
        write(("\n" if number else "") + screen)
        if pause and number < len(screens) - 1:
            wait("\n[Photograph this screen; press Enter for the next one.]")
    write(f"\nThe same pages are in {folder}")
    return folder
