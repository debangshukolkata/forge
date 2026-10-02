"""Pinned context (spec §10.2): re-sent with every model call, never compacted.

Slots: the requirement and tasks, the Mode B host profile essentials, instructions (FORGE.md), skills,
the memory index, databases, files modified (from the workspace change log) and the latest compaction
summary. The rendered block is capped; lowest-priority slots are shortened first.
"""

from __future__ import annotations

from forge.llm.base import Message
from forge.llm.tokens import count_text_tokens

# Highest priority first: when over the cap, later slots are cut before earlier ones.
SLOT_ORDER = [
    "requirement",
    "instructions",
    "phase_and_tasks",
    "compaction_summary",
    "database",
    "kb_essentials",
    "files_modified",
    "memory_index",
    "skills",
]
SLOT_TITLES = {
    "requirement": "Requirement and acceptance criteria",
    "phase_and_tasks": "Phase and tasks",
    "compaction_summary": (
        "Summary of earlier conversation (continue the task from its current state and next step "
        "directly, with tool calls; do not stop to announce it)"
    ),
    "database": "Databases (what Forge may do; DB-backed tests use the scratch schema via PGOPTIONS)",
    "kb_essentials": "Codebase essentials",
    "instructions": "Instructions from FORGE.md files (always follow them)",
    "skills": "Skills",
    "files_modified": "Files modified so far",
    "memory_index": "Memory",
}
HEADER = "Pinned context (kept up to date by Forge; it replaces anything older on the same topics):"


class PinnedBlocks:
    def __init__(self) -> None:
        self.slots: dict[str, str] = {}

    def set(self, slot: str, text: str | None) -> None:
        if slot not in SLOT_TITLES:
            raise ValueError(f"unknown pinned slot {slot!r}")
        if text and text.strip():
            self.slots[slot] = text.strip()
        else:
            self.slots.pop(slot, None)

    def get(self, slot: str) -> str | None:
        return self.slots.get(slot)

    def render(self, cap_tokens: int) -> str:
        if not self.slots:
            return ""
        sections = [
            (slot, f"## {SLOT_TITLES[slot]}\n{self.slots[slot]}") for slot in SLOT_ORDER if slot in self.slots
        ]
        text = HEADER + "\n\n" + "\n\n".join(section for _, section in sections)
        # Over the cap: shorten from the lowest-priority slot upwards.
        for index in range(len(sections) - 1, -1, -1):
            if count_text_tokens(text) <= cap_tokens:
                break
            slot, section = sections[index]
            others = sum(count_text_tokens(s) for i, (_, s) in enumerate(sections) if i != index)
            room = cap_tokens - others - count_text_tokens(HEADER) - 20
            sections[index] = (slot, _shorten(section, max(room, 0)))
            text = HEADER + "\n\n" + "\n\n".join(s for _, s in sections if s)
        return text

    def message(self, cap_tokens: int) -> Message | None:
        text = self.render(cap_tokens)
        return Message.system(text) if text else None


def _shorten(section: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    lines = section.splitlines()
    kept: list[str] = []
    for line in lines:
        if count_text_tokens("\n".join([*kept, line])) > max_tokens - 5:
            kept.append("[… shortened to fit the pinned-context cap]")
            break
        kept.append(line)
    return "\n".join(kept)
