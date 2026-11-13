"""The model's history of one conversation, saved so a reopened project continues it (D-582, CV2).

`history.json` holds what the model was sent, without the system prompt (that is built fresh) and without
anything only a provider can replay (`provider_items`, images). It is redacted before it is written and again
when it is read: a file edited by hand or written by an older version must not bring a secret back into the
model's context. A file that cannot be read whole is ignored; this module never raises for a bad file."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from forge.context.compaction import pairs_are_valid, step_starts
from forge.llm.base import Message
from forge.workspace.workspace import Workspace

HISTORY_VERSION = 1


def save_history(
    workspace: Workspace,
    path: Path,
    messages: list[Message],
    pinned: dict[str, str],
    redact: Callable[[Any], Any],
) -> None:
    """Writes the messages (the system prompt not among them), redacted, through the jail and atomically."""
    dumped = []
    for message in messages:
        item = message.model_dump(mode="json")
        item["provider_items"] = None
        item["provider_items_model"] = None
        item["images"] = []
        dumped.append(item)
    document = {
        "version": HISTORY_VERSION,
        "saved": datetime.now(UTC).isoformat(timespec="seconds"),
        "messages": dumped,
        "pinned": pinned,
    }
    text = json.dumps(redact(document), ensure_ascii=False)
    target = workspace.jail.check(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    scratch = target.with_name(target.name + ".tmp")
    scratch.write_text(text, encoding="utf-8")
    scratch.replace(target)


def load_history(path: Path, redact: Callable[[Any], Any]) -> tuple[list[Message], dict[str, str]] | None:
    """(messages, pinned) with valid call and result pairs, or None when there is no usable file."""
    try:
        document = redact(json.loads(path.read_text(encoding="utf-8")))
        if not isinstance(document, dict) or document.get("version") != HISTORY_VERSION:
            return None
        messages = [Message.model_validate(item) for item in document["messages"]]
        raw_pinned = document.get("pinned", {})
        pinned = {str(k): str(v) for k, v in raw_pinned.items()} if isinstance(raw_pinned, dict) else {}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    return valid_prefix(messages), pinned


def valid_prefix(messages: list[Message]) -> list[Message]:
    """The messages cut back to the last step boundary at which every call has its result (a save made in the
    middle of a step, or a damaged file, must not hand the model an orphaned call)."""
    framed = [Message.system(""), *messages]
    if pairs_are_valid(framed):
        return messages
    for cut in reversed(step_starts(framed)):
        if pairs_are_valid(framed[:cut]):
            return framed[1:cut]
    return []
