"""unpack_presentation and pack_presentation (TODO P2.15, D-321): the raw-file escape hatch for what python-pptx cannot do.

Unpack writes the deck's XML parts to a folder in the project; the model edits them with the ordinary file tools; pack validates the
result against the package rules and writes the .pptx. The checks that protect against hostile files are in `slides/rawpackage.py`."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from pydantic import Field

from forge.errors import ForgeError
from forge.slides import rawpackage
from forge.slides.open_deck import DeckError
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

MANIFEST = rawpackage.MANIFEST
KEY_PARTS = (
    "ppt/presentation.xml",
    "ppt/slides/",
    "ppt/slideMasters/",
    "ppt/slideLayouts/",
    "ppt/theme/",
    "ppt/charts/",
)


def _folder_for(path: str, folder: str) -> str:
    return folder.strip().strip("/") or f"work/{Path(path).stem}_xml"


class UnpackPresentation(Tool):
    name = "unpack_presentation"
    read_only = False
    description = (
        "Last resort for what edit_presentation cannot do (an odd master, a custom animation, SmartArt text, a field python-pptx does "
        "not know): write the deck's XML parts into a folder (pretty-printed; pictures and other binary parts stay in the file). Edit "
        "the XML with the normal file tools, then call pack_presentation. Prefer edit_presentation whenever it can do the job."
    )

    class Args(ToolArgs):
        path: str = Field(description="The .pptx, relative to the repository root")
        folder: str = Field(default="", description="Folder to unpack into (default work/<name>_xml)")

    def summary(self, args: UnpackPresentation.Args) -> str:
        return f"unpack {args.path}"

    async def run(self, args: UnpackPresentation.Args, context: ToolContext) -> ToolResult:
        source = context.workspace.path_of(args.path)
        if not source.is_file() or source.suffix.lower() != ".pptx":
            return ToolResult(ok=False, content=f"No .pptx file at {args.path}.")
        folder = _folder_for(args.path, args.folder)
        try:
            unpacked = await asyncio.to_thread(lambda: rawpackage.unpack(source.read_bytes()))
            for name, content in unpacked.xml.items():
                context.workspace.write_bytes(f"{folder}/{name}", content, "deck unpacked for editing")
            manifest = {"source": args.path, "xml": sorted(unpacked.xml)}
            context.workspace.write_text(
                f"{folder}/{MANIFEST}", json.dumps(manifest, indent=1), "unpack manifest"
            )
        except (ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        key = [n for n in sorted(unpacked.xml) if n.startswith(KEY_PARTS)]
        lines = [
            f"Unpacked {len(unpacked.xml)} XML parts of {args.path} into {folder}/ ({len(unpacked.binary)} binary parts stay in the file).",
            "Main parts:",
            *[f"- {folder}/{n}" for n in key[:60]],
        ]
        if len(key) > 60:
            lines.append(f"... and {len(key) - 60} more")
        if unpacked.external:
            lines.append("The deck links outside itself: " + ", ".join(sorted(set(unpacked.external))[:10]))
        lines.append(
            "Edit with the file tools (change as little as possible; keep every r:id that is used), then pack_presentation. "
            "To add a picture, put the file in the folder under ppt/media/ and add its relationship."
        )
        return ToolResult(ok=True, content="\n".join(lines))


class PackPresentation(Tool):
    name = "pack_presentation"
    read_only = False
    description = (
        "Pack a folder made by unpack_presentation back into a .pptx: the XML parts from the folder, the binary parts from the original "
        "deck, files you added, minus XML parts you deleted. The result is checked against the package rules and nothing is saved when "
        "it would make PowerPoint ask to repair the file; the message says what to fix. Then preview_presentation."
    )

    class Args(ToolArgs):
        folder: str = Field(description="The folder made by unpack_presentation")
        output: str = Field(description="Where to save the .pptx (may be the original: that can be undone)")
        keep_folder: bool = Field(
            default=False, description="Keep the folder afterwards (default: remove it)"
        )

    def summary(self, args: PackPresentation.Args) -> str:
        return f"pack {args.folder} into {args.output}"

    async def run(self, args: PackPresentation.Args, context: ToolContext) -> ToolResult:
        folder = args.folder.strip().strip("/")
        root = context.workspace.path_of(folder)
        manifest_file = root / MANIFEST
        if not manifest_file.is_file():
            return ToolResult(
                ok=False, content=f"{folder} was not made by unpack_presentation (no {MANIFEST})."
            )
        if not args.output.lower().endswith(".pptx"):
            return ToolResult(ok=False, content="Save the result as a .pptx.")
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
            original = context.workspace.path_of(manifest["source"]).read_bytes()
            files = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file() and path.name != MANIFEST
            }
            data, notes = await asyncio.to_thread(rawpackage.pack, original, files, set(manifest["xml"]))
            context.workspace.write_bytes(args.output, data, "deck packed from edited XML")
            if not args.keep_folder:
                for name in [*files, MANIFEST]:
                    context.workspace.delete(f"{folder}/{name}", "unpacked folder removed after packing")
        except DeckError as error:
            return ToolResult(ok=False, content=str(error))
        except (ForgeError, OSError, ValueError, KeyError) as error:
            return ToolResult(ok=False, content=f"Could not pack: {error}")
        context.last_edit_step = context.step
        lines = [
            f"Saved {args.output}.",
            *notes,
            "Next: preview_presentation and look at the slides you changed.",
        ]
        return ToolResult(ok=True, content="\n".join(lines))


def raw_tools() -> list[Tool]:
    return [UnpackPresentation(), PackPresentation()]
