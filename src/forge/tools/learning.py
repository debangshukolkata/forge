"""Learning tools (spec §12.2-12.3): the requirements library (same repository/profile only) and proposing a
lesson mid-run (used only after the user approves it)."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from forge.config import forge_home
from forge.learning.improve import Improvements
from forge.learning.lessons import LessonStore
from forge.learning.library import Library
from forge.learning.scope import scope_of, visible_scopes
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult


def _scopes(context: ToolContext) -> tuple[str, ...]:
    return visible_scopes(scope_of(context.workspace, forge_home()))


class LibrarySearch(Tool):
    name = "library_search"
    read_only = True
    description = (
        "Search earlier requirements done on this same codebase (requirement cards: goal, "
        "approach, decisions, "
        "files, endpoints/tables, problems). Reuse their patterns and cite them by id in the plan."
    )

    class Args(ToolArgs):
        query: str
        limit: int = Field(default=5, ge=1, le=10)

    async def run(self, args: LibrarySearch.Args, context: ToolContext) -> ToolResult:
        hits = Library(forge_home()).search(
            args.query, _scopes(context), limit=args.limit, exclude=str(context.workspace.root)
        )
        if not hits:
            return ToolResult(ok=True, content="No earlier requirements on this codebase match.")
        return ToolResult(ok=True, content="\n\n".join(f"{h.id}: {h.title}\n{h.snippet}" for h in hits))


class LibraryRead(Tool):
    name = "library_read"
    read_only = True
    description = (
        "Read an earlier requirement's card (id, e.g. REQ-0003), or one file from its workspace (path)."
    )

    class Args(ToolArgs):
        id: str
        path: str | None = Field(default=None, description="Optional repo-relative file in that workspace")

    async def run(self, args: LibraryRead.Args, context: ToolContext) -> ToolResult:
        library = Library(forge_home())
        scopes = _scopes(context)
        if args.path:
            text = library.read_workspace_file(args.id, args.path, scopes)
            return ToolResult(
                ok=text is not None,
                content=text if text is not None else f"No file {args.path} in {args.id}.",
            )
        card = library.read(args.id, scopes)
        return ToolResult(ok=card is not None, content=card or f"No requirement {args.id} for this codebase.")


class LessonPropose(Tool):
    name = "lesson_propose"
    read_only = True  # Forge Home only; nothing is used until the user approves it
    description = (
        "Propose a lesson worth keeping for future work on this codebase (e.g. after a fix that took several "
        "attempts): one imperative sentence. It is used only after the user approves it (/lessons)."
    )

    class Args(ToolArgs):
        text: str
        confidence: str = "medium"

    async def run(self, args: LessonPropose.Args, context: ToolContext) -> ToolResult:
        scope = scope_of(context.workspace, forge_home())
        lesson = LessonStore(forge_home()).propose(
            args.text, scope, source="mid-run", confidence=args.confidence
        )
        await context.emit("lesson_proposed", {"id": lesson.id, "text": lesson.text})
        return ToolResult(ok=True, content=f"Proposed as {lesson.id}; the user reviews it with /lessons.")


class ImprovementPropose(Tool):
    name = "improvement_propose"
    read_only = True  # writes a proposal folder in Forge Home; Forge never changes itself
    description = (
        "Draft a proposal to improve Forge itself (spec §12.5): tier 1 = a lesson, tier 2 = text to add to a "
        "built-in prompt (system, system_modeb or phases), tier 3 = a code change as a unified diff against "
        "Forge's source. The user reviews and applies it; tier 3 can be validated with /improve validate."
    )

    class Args(ToolArgs):
        tier: Literal[1, 2, 3]
        title: str
        problem: str
        evidence: str
        change: str
        risk: str
        how_to_test: str
        prompt: Literal["system", "system_modeb", "phases"] | None = None
        override_text: str = ""
        patch: str = ""

    async def run(self, args: ImprovementPropose.Args, context: ToolContext) -> ToolResult:
        if args.tier == 1:
            lesson = LessonStore(forge_home()).propose(
                args.change, "global", source="improvement", evidence=args.evidence
            )
            return ToolResult(
                ok=True, content=f"Tier 1: proposed lesson {lesson.id} (global); approve it with /lessons."
            )
        try:
            proposal = Improvements(forge_home()).create(
                args.tier,
                args.title,
                args.problem,
                args.evidence,
                args.change,
                args.risk,
                args.how_to_test,
                patch=args.patch,
                prompt=args.prompt,
                override_text=args.override_text,
            )
        except ValueError as error:
            return ToolResult(ok=False, content=str(error))
        await context.emit(
            "improvement_proposed", {"id": proposal.id, "title": args.title, "tier": args.tier}
        )
        return ToolResult(
            ok=True,
            content=f"Drafted {proposal.id}. Tell the user in one line; they review it with "
            f"/improve show {proposal.id}.",
        )
