"""The conversations of one project (D-582): each has its own event log, task state and saved model history.

Layout under `<project>/.forge/conversations/`: `index.json` and one folder per conversation (`c1`, `c2`, ...).
Files, changes, memory, knowledge, cost and subagent transcripts stay with the project. Pure file work: no model,
no events. Every write goes through the workspace jail and is atomic (temporary file, then replace)."""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from forge.errors import ConversationError
from forge.workspace.workspace import Workspace

CONVERSATION_ID = re.compile(r"^c[1-9][0-9]{0,5}$")
INDEX_VERSION = 1
TITLE_CHARS = 60
FIRST = "c1"


class Conversation(BaseModel):
    id: str
    title: str = ""
    created: str = ""
    updated: str = ""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _timestamp(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat(timespec="seconds")
    except OSError:
        return _now()


def title_of(text: str) -> str:
    """A message as one line of at most 60 characters."""
    line = " ".join(text.split())
    return line if len(line) <= TITLE_CHARS else line[: TITLE_CHARS - 1].rstrip() + "…"


class ConversationStore:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.root = workspace.forge_dir / "conversations"
        self.index_path = self.root / "index.json"

    # --- the index -------------------------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        """The index; a project that has none is migrated first (section 4 of docs/SPEC_CONVERSATIONS.md)."""
        data = self._read_index()
        if data is None:
            data = self._migrate()
        return data

    def _read_index(self) -> dict[str, Any] | None:
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        valid = isinstance(data, dict) and data.get("version") == INDEX_VERSION
        return (
            data if valid and isinstance(data.get("conversations"), list) and data["conversations"] else None
        )

    def _write(self, path: Path, text: str) -> None:
        target = self.workspace.jail.check(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        scratch = target.with_name(target.name + ".tmp")
        scratch.write_text(text, encoding="utf-8")
        scratch.replace(target)

    def _save(self, data: dict[str, Any]) -> None:
        self._write(self.index_path, json.dumps(data, indent=1, ensure_ascii=False))

    def _migrate(self) -> dict[str, Any]:
        """Copies (never moves) the old log and task state into `c1`; the old files stay as the backup. The index
        is written last, so a crash before it makes the next open start again."""
        forge_dir = self.workspace.forge_dir
        old_log = forge_dir / "transcripts" / "events.jsonl"
        old_state = forge_dir / "state.json"
        folder = self.root / FIRST
        self.workspace.jail.check(folder)
        folder.mkdir(parents=True, exist_ok=True)
        for old, name in ((old_log, "events.jsonl"), (old_state, "state.json")):
            if old.is_file():
                shutil.copyfile(old, self.workspace.jail.check(folder / name))
        first = Conversation(
            id=FIRST,
            title=_title_from_log(old_log),
            created=_timestamp(old_log) if old_log.is_file() else _now(),
            updated=_timestamp(old_log) if old_log.is_file() else _now(),
        )
        data = {"version": INDEX_VERSION, "active": FIRST, "conversations": [first.model_dump()]}
        self._save(data)
        return data

    # --- reading ---------------------------------------------------------------------------------------

    def list(self) -> list[Conversation]:
        return [Conversation(**item) for item in self._load()["conversations"]]

    def get(self, conversation_id: str) -> Conversation:
        self._valid(conversation_id)
        for conversation in self.list():
            if conversation.id == conversation_id:
                return conversation
        raise ConversationError(f"There is no conversation {conversation_id} in this project.")

    def active(self) -> Conversation:
        data = self._load()
        for item in data["conversations"]:
            if item["id"] == data["active"]:
                return Conversation(**item)
        return Conversation(**data["conversations"][0])

    # --- changing --------------------------------------------------------------------------------------

    def create(self, title: str = "") -> Conversation:
        """A new conversation, now the active one. Its task state starts empty except for the cadence of the
        conversation that was active: the user set it by saying so and it must not be lost."""
        data = self._load()
        previous = self.state_path(data["active"])
        number = max(int(item["id"][1:]) for item in data["conversations"]) + 1
        created = Conversation(id=f"c{number}", title=title_of(title), created=_now(), updated=_now())
        folder = self.root / created.id
        self.workspace.jail.check(folder)
        folder.mkdir(parents=True, exist_ok=True)
        cadence = _cadence_of(previous)
        if cadence is not None:
            self._write(folder / "state.json", json.dumps({"cadence": cadence}))
        data["conversations"].append(created.model_dump())
        data["active"] = created.id
        self._save(data)
        return created

    def activate(self, conversation_id: str) -> Conversation:
        conversation = self.get(conversation_id)
        data = self._load()
        data["active"] = conversation.id
        self._save(data)
        return conversation

    def rename(self, conversation_id: str, title: str) -> Conversation:
        return self._change(conversation_id, title=title_of(title))

    def touch(self, conversation_id: str) -> None:
        self._change(conversation_id, updated=_now())

    def set_title_if_empty(self, conversation_id: str, text: str) -> None:
        if not self.get(conversation_id).title and title_of(text):
            self._change(conversation_id, title=title_of(text))

    def _change(self, conversation_id: str, **fields: str) -> Conversation:
        self._valid(conversation_id)
        data = self._load()
        for item in data["conversations"]:
            if item["id"] == conversation_id:
                item.update(fields)
                self._save(data)
                return Conversation(**item)
        raise ConversationError(f"There is no conversation {conversation_id} in this project.")

    # --- paths -----------------------------------------------------------------------------------------

    @staticmethod
    def _valid(conversation_id: str) -> None:
        if not isinstance(conversation_id, str) or not CONVERSATION_ID.match(conversation_id):
            raise ConversationError("That is not a conversation id.")

    def folder(self, conversation_id: str) -> Path:
        """The conversation's folder, checked to lie inside `conversations/` (an id comes from the browser)."""
        self._valid(conversation_id)
        folder = (self.root / conversation_id).resolve()
        if self.root.resolve() not in folder.parents:
            raise ConversationError("That is not a conversation id.")
        return folder

    def events_path(self, conversation_id: str) -> Path:
        return self.folder(conversation_id) / "events.jsonl"

    def history_path(self, conversation_id: str) -> Path:
        return self.folder(conversation_id) / "history.json"

    def state_path(self, conversation_id: str) -> Path:
        return self.folder(conversation_id) / "state.json"


def _title_from_log(log: Path) -> str:
    """The first user message of an old log, as a title (empty when there is none)."""
    try:
        with log.open(encoding="utf-8") as handle:
            for line in handle:
                if '"user_message"' not in line:
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("type") == "user_message":
                    return title_of(str(event.get("payload", {}).get("text", "")))
    except OSError:
        return ""
    return ""


def _cadence_of(state_path: Path) -> str | None:
    try:
        value = json.loads(state_path.read_text(encoding="utf-8")).get("cadence")
    except (OSError, ValueError, AttributeError):
        return None
    return value if isinstance(value, str) and value != "default" else None


def conversation_file(root: Path, name: str, conversation_id: str | None = None) -> Path:
    """Where a conversation's `events.jsonl` or `state.json` is, from the project folder alone and without
    changing anything (the project list and the command line read many projects). A project that has no index
    yet keeps both files at their old places."""
    forge_dir = root / ".forge"
    old = forge_dir / "transcripts" / name if name == "events.jsonl" else forge_dir / name
    try:
        index = json.loads((forge_dir / "conversations" / "index.json").read_text(encoding="utf-8"))
        chosen = conversation_id or index["active"]
    except (OSError, ValueError, KeyError, TypeError):
        return old
    if not isinstance(chosen, str) or not CONVERSATION_ID.match(chosen):
        return old
    return forge_dir / "conversations" / chosen / name
