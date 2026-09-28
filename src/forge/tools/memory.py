"""Memory tools (spec §9.9): read the user's memories; save one when the user states a lasting
preference. The memory index (titles) is pinned in every session."""

from __future__ import annotations

from forge.config import forge_home
from forge.memory.store import MemoryStore
from forge.tools.base import Tool, ToolArgs, ToolContext, ToolResult


class MemoryRead(Tool):
    name = "memory_read"
    read_only = True
    description = (
        "Read the user's saved memories (preferences for all repositories); id = one memory, empty = all."
    )

    class Args(ToolArgs):
        id: str | None = None

    async def run(self, args: MemoryRead.Args, context: ToolContext) -> ToolResult:
        store = MemoryStore(forge_home())
        if args.id:
            memory = store.get(args.id)
            return ToolResult(
                ok=memory is not None, content=memory.text if memory else f"No memory {args.id}."
            )
        memories = store.all()
        return ToolResult(
            ok=True, content="\n\n".join(f"{m.id}: {m.text}" for m in memories) or "No memories."
        )


class MemoryWrite(Tool):
    name = "memory_write"
    read_only = True  # writes only to Forge Home, never the workspace or the user's repository
    description = (
        "Save a lasting preference the user just stated for all future work (e.g. 'always use type hints'). "
        "Only for explicit user preferences — never code, secrets or facts about this repository."
    )

    class Args(ToolArgs):
        text: str

    async def run(self, args: MemoryWrite.Args, context: ToolContext) -> ToolResult:
        memory = MemoryStore(forge_home()).add(args.text)
        await context.emit("notice", {"kind": "memory", "text": f"Remembered ({memory.id}): {memory.title}"})
        return ToolResult(ok=True, content=f"Saved as {memory.id}.")
