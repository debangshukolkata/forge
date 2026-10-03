"""The full result of a tool call, kept for the web UI (D-195).

The `tool_call_finished` event carries only a short preview (the event log is replayed on every reopen, so it
must stay small). When a result is longer, the whole text is saved here, redacted, and the event says where:
the UI offers "Show full output" and fetches it on demand. Files live in the workspace's own `.forge` folder,
written through the write jail like every other internal file."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from forge.workspace.workspace import Workspace

FOLDER = "tool-output"
MAX_SAVED_CHARS = 2_000_000  # a runaway log must not fill the disk; the cut is said in the text itself
CUT_NOTE = f"\n… (output cut at {MAX_SAVED_CHARS:,} characters)"


def save_full_output(workspace: Workspace, content: str, redact: Callable[[str], str]) -> str | None:
    """Returns the id to fetch the text by, or None when it could not be saved (the preview still shows)."""
    text = redact(content)
    if len(text) > MAX_SAVED_CHARS:
        text = text[:MAX_SAVED_CHARS] + CUT_NOTE
    output_id = uuid.uuid4().hex
    try:
        path = workspace.jail.check(workspace.forge_dir / FOLDER / f"{output_id}.txt")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError:
        return None
    return output_id
