"""Session management (spec §13B): `forge sessions list` (recent workspaces and their state) and
`/export-chat` (the conversation as Markdown, from the event log)."""

from __future__ import annotations

import contextlib
import json
from datetime import datetime
from pathlib import Path

from forge.config import forge_home
from forge.protocol.events import Event, EventType
from forge.workspace.workspace import Workspace


def list_sessions(home: Path | None = None) -> str:
    home = home or forge_home()
    recent_file = home / "recent_workspaces.json"
    try:
        entries = json.loads(recent_file.read_text(encoding="utf-8")) if recent_file.exists() else []
    except ValueError:
        entries = []
    lines = []
    for number, entry in enumerate(entries, 1):
        root = Path(entry["path"])
        state_file = root / ".forge" / "state.json"
        phase = "?"
        if state_file.exists():
            with contextlib.suppress(ValueError):
                phase = json.loads(state_file.read_text(encoding="utf-8")).get("phase", "?")
        lines.append(f"{number:>3}. {entry.get('name', root.name)}  [{phase}]  {root}")
    if not lines:
        return "No sessions yet. Start one with: forge new ... then forge --workspace <path> (or forge ui)."
    return "\n".join(lines) + "\n\nResume one with: forge resume --workspace <path>"


def export_chat(workspace: Workspace, events: list[Event]) -> Path:
    lines = [f"# Conversation — {workspace.info.name}", "", f"Exported {datetime.now():%Y-%m-%d %H:%M}", ""]
    for event in events:
        payload = event.payload
        if event.type == EventType.USER_MESSAGE:
            lines += ["## You", "", str(payload.get("text", "")), ""]
        elif event.type == EventType.MESSAGE_DONE and payload.get("text"):
            lines += ["## Forge", "", str(payload["text"]), ""]
        elif event.type == EventType.TOOL_CALL_STARTED:
            lines.append(f"> tool: {payload.get('name')} — {payload.get('summary', '')}")
        elif event.type == EventType.QUESTION_ASKED:
            lines += [f"> question: {payload.get('question')}", ""]
        elif event.type == EventType.APPROVAL_REQUESTED:
            lines.append(f"> approval requested: {payload.get('summary') or payload.get('tool')}")
    folder = workspace.jail.check(workspace.forge_dir / "exports")
    folder.mkdir(parents=True, exist_ok=True)
    path = workspace.jail.check(folder / f"chat-{datetime.now():%Y%m%d-%H%M%S}.md")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
