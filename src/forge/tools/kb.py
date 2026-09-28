"""Knowledge Base tools (spec §9.2, §9.9): kb_search, kb_read, find_symbol, find_references, list_symbols."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from forge.tools.base import Tool, ToolArgs, ToolContext, ToolResult

NO_KB = (
    "There is no knowledge base for this repository yet. Use grep/glob/read_file, or ask the user to run "
    "/kb build."
)


class KbSearch(Tool):
    name = "kb_search"
    read_only = True
    description = (
        "Search the repository's knowledge base: architecture, conventions, API catalog, DB schema, "
        "LLM graphs, "
        "per-package docs, and code symbols. Use it before exploring files by hand."
    )

    class Args(ToolArgs):
        query: str
        kinds: list[Literal["doc", "symbol"]] | None = Field(
            default=None, description="Limit to docs or symbols."
        )

    def summary(self, args: KbSearch.Args) -> str:
        return f"kb search {args.query!r}"

    async def run(self, args: KbSearch.Args, context: ToolContext) -> ToolResult:
        if context.kb is None:
            return ToolResult(ok=True, content=NO_KB)
        hits = context.kb.search(args.query, list(args.kinds) if args.kinds else None)
        if not hits:
            return ToolResult(ok=True, content="No matches.")
        return ToolResult(
            ok=True,
            content="\n\n".join(f"[{hit.kind}] {hit.name} — {hit.location}\n{hit.snippet}" for hit in hits),
        )


class KbRead(Tool):
    name = "kb_read"
    read_only = True
    description = (
        "Read a whole knowledge-base document, e.g. ARCHITECTURE, CONVENTIONS, API_CATALOG, DB_SCHEMA, "
        "LLM_GRAPHS, STACK, COMMANDS or modules/<package>."
    )

    class Args(ToolArgs):
        doc: str

    def summary(self, args: KbRead.Args) -> str:
        return f"kb read {args.doc}"

    async def run(self, args: KbRead.Args, context: ToolContext) -> ToolResult:
        if context.kb is None:
            return ToolResult(ok=True, content=NO_KB)
        text = context.kb.read(args.doc)
        if text is None:
            return ToolResult(
                ok=False, content=f"No document '{args.doc}'. Available: {', '.join(context.kb.doc_names())}"
            )
        return ToolResult(ok=True, content=text)


class FindSymbol(Tool):
    name = "find_symbol"
    read_only = True
    description = (
        "Find where a class, function or method is defined (exact or qualified name), with its signature."
    )

    class Args(ToolArgs):
        name: str

    async def run(self, args: FindSymbol.Args, context: ToolContext) -> ToolResult:
        if context.kb is None:
            return ToolResult(ok=True, content=NO_KB)
        rows = context.kb.find_symbol(args.name)
        if not rows:
            return ToolResult(ok=True, content=f"No symbol named {args.name}.")
        return ToolResult(
            ok=True,
            content="\n".join(
                f"{r['kind']} {r['qualname']} — {r['path']}:{r['line']}"
                + (f"\n    {r['signature']}" if r["signature"] else "")
                + (f"\n    decorators: {', '.join(r['decorators'])}" if r["decorators"] else "")  # type: ignore[arg-type]
                + (f"\n    bases: {', '.join(r['bases'])}" if r["bases"] else "")  # type: ignore[arg-type]
                for r in rows
            ),
        )


class FindReferences(Tool):
    name = "find_references"
    read_only = True
    description = (
        "Find where a function or class is called or used (by name), across the original repository."
    )

    class Args(ToolArgs):
        name: str

    async def run(self, args: FindReferences.Args, context: ToolContext) -> ToolResult:
        if context.kb is None:
            return ToolResult(ok=True, content=NO_KB)
        rows = context.kb.find_references(args.name)
        return ToolResult(
            ok=True, content="\n".join(f"{path}:{line}" for path, line in rows) or "No references."
        )


class ListSymbols(Tool):
    name = "list_symbols"
    read_only = True
    description = "List the classes, functions and methods defined in one file (repository-relative path)."

    class Args(ToolArgs):
        path: str

    async def run(self, args: ListSymbols.Args, context: ToolContext) -> ToolResult:
        if context.kb is None:
            return ToolResult(ok=True, content=NO_KB)
        rows = context.kb.list_symbols(args.path)
        return ToolResult(
            ok=True,
            content="\n".join(
                f"{line:>5}  {kind:<8} {qualname}  {signature}" for kind, qualname, line, signature in rows
            )
            or "No symbols.",
        )
