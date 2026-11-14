"""The field log: facts about what DebCraft did on a machine DebCraft cannot see, one JSON line each (D-615).

The open items that need the user's office laptop (the first sign-in, the tunnel, the relay with the drivers of a
real application) are closed from facts the user photographs. Most facts are in the project's event log; these are
not, because they happen outside a conversation (a sign-in made by a tool, the relay of the development database,
the listener that refuses the held-back settings). They go to `<DebCraft Home>/logs/field.jsonl`.

Names, counts, seconds and the first words of an error only: a caller never passes a token, a password or a file
content, and every line passes the redactor once more before it is written. Writing never raises: a log that
cannot be written must not stop a sign-in or a connection.
"""

from __future__ import annotations

import contextlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from forge.config import forge_home
from forge.safety.redact import default_redactor

LOG_NAME = "field.jsonl"
MAX_BYTES = 1_000_000
KEEP_LINES = 1500
MAX_TEXT = 160


def log_path(home: Path | None = None) -> Path:
    return (home or forge_home()) / "logs" / LOG_NAME


def _plain(value: Any) -> Any:
    if isinstance(value, bool | int | float) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in list(value.items())[:40]}
    if isinstance(value, list | tuple | set):
        return [_plain(item) for item in list(value)[:40]]
    text = " ".join(str(value).split())
    return text[:MAX_TEXT] + ("..." if len(text) > MAX_TEXT else "")


def write(kind: str, home: Path | None = None, **fields: Any) -> None:
    """Appends one line. `kind` names the fact (`sign_in`, `relay_start`, `relay_stop`, `relay_error`, ...)."""
    with contextlib.suppress(OSError, ValueError, TypeError):
        path = log_path(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {"ts": datetime.now().isoformat(timespec="seconds"), "kind": kind, **_plain(fields)}
        line = default_redactor.redact(json.dumps(record, ensure_ascii=False))
        if path.is_file() and path.stat().st_size > MAX_BYTES:
            kept = path.read_text(encoding="utf-8", errors="replace").splitlines()[-KEEP_LINES:]
            path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def read(kinds: tuple[str, ...] | None = None, home: Path | None = None) -> list[dict[str, Any]]:
    """The records written so far, oldest first; the ones of the given kinds only when `kinds` is set."""
    try:
        lines = log_path(home).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    records: list[dict[str, Any]] = []
    for line in lines:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict) and (kinds is None or record.get("kind") in kinds):
            records.append(record)
    return records
