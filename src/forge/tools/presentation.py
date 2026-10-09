"""build_presentation and preview_presentation (D-240): make a real .pptx from an outline, then look at it.

The skill `make-presentation` teaches how to write the outline and how to work: outline, build, preview, fix.
These tools run inside Forge itself (python-pptx is Forge's optional extra `slides`), so they do not depend on
the project's own Python environment."""

from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import Field

from forge.errors import ForgeError
from forge.slides import preview
from forge.slides.build import SlidesUnavailable, build_deck
from forge.slides.spec import parse_deck
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.vision import image_path

PREVIEW_FOLDER = ".forge/reports/slides"


class BuildPresentation(Tool):
    name = "build_presentation"
    read_only = False
    description = (
        "Make a PowerPoint (.pptx) from an outline file you wrote (JSON or YAML; load the "
        "`make-presentation` skill for its format and the design rules). Slides get real titles, text "
        "boxes, native charts and tables, speaker notes, and text sized to fit. Returns per-slide warnings "
        "(text too long, too many bullets, ...) that you should fix by editing the outline and building "
        "again. Then call preview_presentation and look at the pictures."
    )

    class Args(ToolArgs):
        outline: str = Field(description="Path of the JSON or YAML outline, relative to the repository root")
        output: str = Field(description="Path of the .pptx to write, e.g. docs/q3-review.pptx")
        reason: str = Field(default="", description="One line saying why; shown to the user in CHANGES.md.")

    def summary(self, args: BuildPresentation.Args) -> str:
        return f"build presentation {args.output}"

    async def run(self, args: BuildPresentation.Args, context: ToolContext) -> ToolResult:
        if not args.output.lower().endswith(".pptx"):
            return ToolResult(ok=False, content="The output file name must end in .pptx")
        outline = context.workspace.path_of(args.outline)
        if not outline.is_file():
            return ToolResult(ok=False, content=f"No outline file at {args.outline}. Write it first.")
        try:
            deck = parse_deck(
                outline.read_text(encoding="utf-8"), as_yaml=outline.suffix.lower() in {".yaml", ".yml"}
            )
            built = await asyncio.to_thread(
                build_deck, deck, lambda name: image_path(context, name).read_bytes()
            )
            context.workspace.write_bytes(
                args.output, built.data, args.reason or "presentation built from an outline"
            )
        except SlidesUnavailable as error:
            return ToolResult(
                ok=False, content=f"{error} Tell the user; a presentation cannot be built without it."
            )
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        context.last_edit_step = context.step
        warnings = [f"slide {s.number} ({s.layout}): {w}" for s in built.slides for w in s.warnings]
        lines = [f"Built {args.output}: {len(built.slides)} slides, {len(built.data) // 1024} KB."]
        lines += (
            ["Fix these in the outline and build again:", *[f"- {w}" for w in warnings]]
            if warnings
            else ["No layout warnings."]
        )
        lines.append("Next: preview_presentation to look at the slides.")
        return ToolResult(ok=True, content="\n".join(lines))


class PreviewPresentation(Tool):
    name = "preview_presentation"
    read_only = False
    description = (
        "Make a picture of every slide of a .pptx with PowerPoint itself (Windows with PowerPoint "
        "installed), so you can look at them with view_image and fix what looks wrong: crowded or cut-off "
        "text, uneven spacing, a chart that is hard to read. If PowerPoint is not available it says so, and "
        "you rely on the build warnings instead."
    )

    class Args(ToolArgs):
        path: str = Field(description="The .pptx to preview, relative to the repository root")

    def summary(self, args: PreviewPresentation.Args) -> str:
        return f"preview {args.path}"

    async def run(self, args: PreviewPresentation.Args, context: ToolContext) -> ToolResult:
        deck = context.workspace.path_of(args.path)
        if not deck.is_file() or deck.suffix.lower() != ".pptx":
            return ToolResult(ok=False, content=f"No .pptx file at {args.path}.")
        folder = context.workspace.jail.check(context.workspace.root / PREVIEW_FOLDER / deck.stem)
        try:
            pictures = await asyncio.to_thread(preview.export_slides, deck, folder)
        except preview.PreviewUnavailable as error:
            return ToolResult(
                ok=True,
                content=f"No pictures could be made: {error} Go by the build warnings, and tell the user "
                "the slides were not looked at.",
            )
        names = [self.relative(context, picture) for picture in pictures]
        return ToolResult(
            ok=True,
            content="Pictures of the slides (look at each with view_image and fix what is wrong):\n"
            + "\n".join(f"- {name}" for name in names),
        )

    @staticmethod
    def relative(context: ToolContext, path: Path) -> str:
        return path.resolve().relative_to(context.workspace.root.resolve()).as_posix()


def presentation_tools() -> list[Tool]:
    return [BuildPresentation(), PreviewPresentation()]
