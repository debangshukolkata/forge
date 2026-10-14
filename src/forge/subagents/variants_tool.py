"""build_variants: several independent variants of one thing, built at the same time (TODO X8, D-380).

The first benchmark of "three throwaway designs" showed that advice is not enough: the model loaded the parallel-builders skill, then decided to "treat this as a single-agent
job to minimise coordination errors" and built all three itself, one after another. This tool makes the parallel route one call: the shared requirement once, and for each
variant a name, a folder and what makes it different. Each variant gets its own builder (own folder, own shell, own port); at most `limits.max_parallel_builders` run at once;
the reports come back together and the main agent verifies and compares them. Lives with the agent code because it starts agents; subagents never get it."""

from __future__ import annotations

import asyncio

from pydantic import Field

from forge.subagents.builder import result_text
from forge.subagents.spawn_tool import run_builder
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.toolkit.folders import clean_folder, folders_disjoint

PAGE_RULES = (
    "If your variant is a page or a screen: write your own DESIGN.md in your folder first (the ui-design-quality skill, token format: colours, typography, rounded, spacing, "
    "components and a composition from find_asset), export its tokens (design_md_export) and build from them, fetch the fonts your tokens name, then look at the result in a "
    "browser at desktop and phone width and fix what the style audit reports before you finish. Do not share files or styles with the other variants: each folder must stand alone."
)
MAX_VARIANTS = 6


class Variant(ToolArgs):
    name: str = Field(description="a short name, e.g. a, b, c or warm-editorial")
    folder: str = Field(
        description="its own folder below the repository root, e.g. designs/design-a (no folder inside another)"
    )
    direction: str = Field(
        description="what makes this variant different: the concept, mood, palette, type and layout idea, or the approach"
    )


class BuildVariants(Tool):
    name = "build_variants"
    read_only = True
    description = (
        "Build 2 to 6 independent variants of one thing AT THE SAME TIME, each by its own builder in its own folder: three designs of a screen, two layouts, A/B options, alternative "
        "implementations. Use it whenever the request asks for several versions, options or alternatives that do not depend on each other: building them yourself one after "
        "another takes as many times as long. Give the shared requirement once (exact facts, names, numbers, what to check) and, for each variant, a name, a folder and what makes it "
        "different. At most limits.max_parallel_builders run at once. You get every builder's report and status back; then verify each result yourself (open it, screenshots at "
        "desktop and phone width, compare_designs for pages) and have the design reviewed once for the whole."
    )

    class Args(ToolArgs):
        brief: str = Field(
            description="the requirement every variant must meet, with the exact facts; a builder sees only this and its own direction"
        )
        variants: list[Variant] = Field(min_length=2, max_length=MAX_VARIANTS)

    def summary(self, args: BuildVariants.Args) -> str:
        return f"build {len(args.variants)} variants: " + ", ".join(v.name for v in args.variants)

    async def run(self, args: BuildVariants.Args, context: ToolContext) -> ToolResult:
        if context.router is None:
            return ToolResult(ok=False, content="No model is available to start builders.")
        names = [v.name.strip().lower() for v in args.variants]
        folders = [clean_folder(v.folder) for v in args.variants]
        if len(set(names)) != len(names) or not all(names):
            return ToolResult(ok=False, content="Give every variant its own short name.")
        for index, folder in enumerate(folders):
            if not folder:
                return ToolResult(
                    ok=False,
                    content=f"Variant {args.variants[index].name!r}: the folder must be below the repository root (no '..', no drive).",
                )
            for other in folders[:index]:
                if not folders_disjoint(folder, other):
                    return ToolResult(
                        ok=False,
                        content=f"The folders {folder!r} and {other!r} overlap: every variant needs a folder of its own, none inside another.",
                    )
        limit = max(1, int(context.router.config.limits.max_parallel_builders))
        gate = asyncio.Semaphore(limit)
        await context.emit(
            "notice",
            {
                "kind": "task",
                "text": f"Building {len(args.variants)} variants"
                + (f", {limit} at a time" if limit < len(args.variants) else " in parallel")
                + ": "
                + ", ".join(f"{n} in {f}" for n, f in zip(names, folders, strict=True)),
            },
        )

        async def build(index: int) -> tuple[str, str, str, str, str]:
            variant = args.variants[index]
            others = "\n".join(
                f"- {args.variants[i].name}: {args.variants[i].direction}"
                for i in range(len(args.variants))
                if i != index
            )
            task = (
                f"Shared requirement (do not build outside your folder):\n{args.brief}\n\n"
                f"YOUR VARIANT: {variant.name}\nWhat makes it different: {variant.direction}\n\n"
                f"The other variants (yours must not look, read or work like them):\n{others}\n\n{PAGE_RULES}"
            )
            async with gate:
                status, report, saved = await run_builder(
                    context, folder=folders[index], name=safe_variant_name(names[index]), task=task
                )
            return names[index], folders[index], status, report, saved

        results = await asyncio.gather(*(build(i) for i in range(len(args.variants))))
        context.note_edit(*(f"{folder}/index.html" for folder in folders))
        if any(_has_page(context, folder) for folder in folders):
            context.last_ui_edit_step = (
                context.step
            )  # task_update asks for a look in a browser and the critic, as for the main agent's own pages
        parts = [
            result_text(name, folder, status, report, saved)
            for name, folder, status, report, saved in results
        ]
        problems = [name for name, _, status, *_ in results if status in ("BLOCKED", "NEEDS_CONTEXT")]
        tail = (
            "\n\nNext: verify every variant yourself (open each, screenshots at desktop and phone width, compare_designs), fix or re-brief what failed, then have the design "
            "reviewed once for the whole."
        )
        if problems:
            tail += f" Not finished: {', '.join(problems)}."
        return ToolResult(ok=True, content="\n\n".join(parts) + tail)


def safe_variant_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in name).strip("-") or "variant"


def _has_page(context: ToolContext, folder: str) -> bool:
    root = context.workspace.path_of(folder)
    return root.is_dir() and any(
        next(root.rglob(pattern), None) is not None
        for pattern in ("*.html", "*.tsx", "*.jsx", "*.vue", "*.css")
    )
