"""The "open an existing project" list (D-184): each known project with when it was last used and what the
user last asked for, read from the tail of its event log so a long project doesn't slow the screen down."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TAIL_BYTES = 256 * 1024
SUMMARY_CHARS = 160


def _event_log(root: Path) -> Path:
    return root / ".forge" / "transcripts" / "events.jsonl"


def _last_request(log: Path) -> str:
    try:
        with log.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - TAIL_BYTES))
            tail = handle.read().decode("utf-8", errors="ignore")
    except OSError:
        return ""
    for line in reversed(tail.splitlines()):
        try:
            event = json.loads(line)
        except ValueError:
            continue  # the first line of a tail read can be cut in half
        if event.get("type") == "user_message":
            text = " ".join(str(event.get("payload", {}).get("text", "")).split())
            return text if len(text) <= SUMMARY_CHARS else text[: SUMMARY_CHARS - 1] + "…"
    return ""


def describe_projects(recent: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`recent` is WebSessionManager.recent(): path, name, repo, app_folder. Newest activity first."""
    projects = []
    for entry in recent:
        root = Path(entry["path"])
        log = _event_log(root)
        try:
            touched = log.stat().st_mtime
        except OSError:
            try:
                touched = (root / ".forge" / "workspace.json").stat().st_mtime
            except OSError:
                continue
        projects.append(
            {
                **entry,
                "mode": "B" if str(entry.get("repo", "")).startswith("standalone") else "A",
                "last_activity": datetime.fromtimestamp(touched, UTC).isoformat(),
                "last_request": _last_request(log),
            }
        )
    return sorted(projects, key=lambda project: project["last_activity"], reverse=True)
