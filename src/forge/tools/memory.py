"""Memory tools (spec §9.9 as amended by D-156): read, save and forget memories. Two scopes: `user`
(everywhere) and `project` (this repository or host profile only). The memory index is pinned in every
session."""

from __future__ import annotations

from typing import Literal

from forge.config import forge_home
from forge.memory.scope import scope_of
from forge.memory.store import KINDS, MemoryStore
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

ScopeName = Literal["user", "project"]


def _store(context: ToolContext, scope: ScopeName) -> MemoryStore:
    return MemoryStore(forge_home(), scope_of(context.workspace) if scope == "project" else None)


class MemoryRead(Tool):
    name = "memory_read"
    read_only = True
    description = (
        "Read saved memories in full: one by name, or all of a scope (user = preferences for every project; "
        "project = what was learned about this repository or host)."
    )

    class Args(ToolArgs):
        name: str | None = None
        scope: ScopeName | None = None  # empty = both

    async def run(self, args: MemoryRead.Args, context: ToolContext) -> ToolResult:
        scopes: list[ScopeName] = [args.scope] if args.scope else ["user", "project"]
        found = [
            m
            for scope in scopes
            for m in _store(context, scope).all()
            if not args.name or m.name == args.name
        ]
        if not found:
            return ToolResult(
                ok=not args.name, content=f"No memory {args.name}." if args.name else "No memories."
            )
        return ToolResult(
            ok=True, content="\n\n".join(f"{m.name} [{m.scope}, {m.kind}]: {m.text}" for m in found)
        )


class MemoryWrite(Tool):
    name = "memory_write"
    read_only = True  # writes only to Forge Home, never the workspace or the user's repository
    description = (
        "Save something worth remembering in later sessions: a preference or correction the user stated "
        "(type user/feedback), a fact about this project that code and git don't show (project), or where to "
        "find something (reference). scope 'project' (default) stays with this repository/host; 'user' "
        "applies "
        "everywhere. Writing an existing name replaces it. Never code, secrets, data rows or what the repo "
        "already shows."
    )

    class Args(ToolArgs):
        name: str
        description: str  # one line, shown in the index
        type: Literal["user", "feedback", "project", "reference"] = "project"
        text: str
        scope: ScopeName = "project"

    async def run(self, args: MemoryWrite.Args, context: ToolContext) -> ToolResult:
        assert args.type in KINDS
        try:
            memory = _store(context, args.scope).save(args.name, args.description, args.type, args.text)
        except ValueError as error:
            return ToolResult(ok=False, content=str(error))
        await context.emit(
            "notice", {"kind": "memory", "text": f"Remembered ({memory.name}): {memory.description}"}
        )
        return ToolResult(ok=True, content=f"Saved as {memory.name} ({args.scope}).")


class MemoryForget(Tool):
    name = "memory_forget"
    read_only = True  # Forge Home only
    description = "Delete a saved memory by name (when it is wrong or the user asks to forget it)."

    class Args(ToolArgs):
        name: str
        scope: ScopeName = "project"

    async def run(self, args: MemoryForget.Args, context: ToolContext) -> ToolResult:
        removed = _store(context, args.scope).delete(args.name)
        return ToolResult(ok=removed, content="Forgotten." if removed else f"No memory {args.name}.")
