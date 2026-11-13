"""What a session does about its conversation (D-582): load the saved model history, save it after every
finished step, name the conversation from the first message, tell the model about the others, and say so
when an old conversation has no saved history. The file work is in `workspace/conversations.py` and
`engine/history_store.py`; this ties it to one `SessionHost`."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from forge.engine.history_store import load_history, save_history
from forge.protocol.events import EventType
from forge.workspace.conversations import ConversationStore
from forge.workspace.workspace import Workspace

if TYPE_CHECKING:
    from forge.engine.session_host import SessionHost

SAVE_EVERY_S = 1.0  # steps can be fast: a save at most once a second, and always at the end of a turn
OTHERS_SHOWN = 10
NOT_RESTORED_TEXT = (
    "What is above this line is no longer in DebCraft's working memory: this conversation was held before "
    "conversations were saved. The files, the notes and the to-do list are kept. Say what you want to "
    "continue with, or start a new conversation."
)


class SessionConversations:
    def __init__(self, workspace: Workspace) -> None:
        self.store = ConversationStore(workspace)
        self.workspace = workspace
        self.conversation_id = self.store.active().id
        self.restored = False
        self.log_had_messages = False
        self._last_save = 0.0
        self._warned = False

    def restore(self, host: SessionHost) -> None:
        """Puts the saved messages behind the system prompt; the compaction summary goes back into its pin."""
        self.remember_log(host)
        loaded = load_history(self.store.history_path(self.conversation_id), host.bus.redact_data)
        if loaded is None:
            return
        messages, pinned = loaded
        host.history = [host.history[0], *messages]
        if pinned.get("compaction_summary"):
            host.context_manager.pinned.set("compaction_summary", pinned["compaction_summary"])
        self.restored = True

    def pin_others(self, host: SessionHost) -> None:
        others = [c for c in self.store.list() if c.id != self.conversation_id]
        if not others:
            return
        lines = [
            f'{c.id} "{c.title or "(no title yet)"}" ({c.updated[:10]})'
            for c in sorted(others, key=lambda item: item.updated, reverse=True)[:OTHERS_SHOWN]
        ]
        lines.append("Earlier conversations of this project can be read with conversation_recall.")
        host.context_manager.pinned.set("conversations", "\n".join(lines))

    def name_from(self, text: str) -> None:
        self.store.set_title_if_empty(self.conversation_id, text)

    async def save(self, host: SessionHost, *, force: bool = False) -> None:
        """Saves the history of the last finished step (a snapshot; the file work runs in a thread)."""
        now = time.monotonic()
        if not force and now - self._last_save < SAVE_EVERY_S:
            return
        self._last_save = now
        messages = list(host.history[1:])
        summary = host.context_manager.pinned.get("compaction_summary")
        pinned = {"compaction_summary": summary} if summary else {}
        try:
            await asyncio.to_thread(
                save_history,
                self.workspace,
                self.store.history_path(self.conversation_id),
                messages,
                pinned,
                host.bus.redact_data,
            )
            if force:
                await asyncio.to_thread(self.store.touch, self.conversation_id)
        except Exception as error:  # a failed save never ends a turn; say so once
            if not self._warned:
                self._warned = True
                await host.bus.publish(
                    EventType.NOTICE,
                    {
                        "kind": "history_not_saved",
                        "text": f"The conversation could not be saved for the next time ({type(error).__name__}).",
                    },
                )

    def remember_log(self, host: SessionHost) -> None:
        """Whether the log already held a user message when this session opened: a message sent after that is not
        history that went missing."""
        self.log_had_messages = any(
            event.type == EventType.USER_MESSAGE for event in host.bus.events_since(0)
        )

    async def notice_if_not_restored(self, host: SessionHost) -> None:
        """An old conversation that has messages in its log but no saved history says so once: not again while
        no user message has come after the notice."""
        if self.restored or not self.log_had_messages:
            return
        events = host.bus.events_since(0)
        last_user = max((e.seq for e in events if e.type == EventType.USER_MESSAGE), default=0)
        if any(
            e.type == EventType.NOTICE
            and e.payload.get("kind") == "history_not_restored"
            and e.seq > last_user
            for e in events
        ):
            return
        await host.bus.publish(EventType.NOTICE, {"kind": "history_not_restored", "text": NOT_RESTORED_TEXT})
