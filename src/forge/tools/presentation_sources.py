"""read_source_document (TODO P2.19, D-338): a Word, Excel, CSV or PDF file as a digest to build a deck from."""

from __future__ import annotations

import asyncio

from pydantic import Field

from forge.errors import ForgeError
from forge.slides.sources import SourceError, describe_digest, read_source
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.vision import image_path

MAX_BYTES = 60 * 1024 * 1024


class ReadSourceDocument(Tool):
    name = "read_source_document"
    read_only = True
    description = (
        "Read a Word (.docx), Excel (.xlsx), CSV or PDF file as a digest for building a presentation: Word as headings with their text, "
        "bullets and tables; Excel and CSV as sheets with columns, sample rows, min/max/total/last of every numeric column and chart-ready "
        "series with the cell range they came from; PDF as text per page. Every fact says where it came from, so the slide notes can cite it "
        "('Source: report.docx, section Results'). A deck says what its sources say: never add a number the digest does not hold."
    )

    class Args(ToolArgs):
        path: str = Field(
            description="The document, relative to the repository root (or a file the user opened)"
        )
        max_chars: int = Field(
            default=9000, ge=1000, le=40000, description="How much of the digest to return"
        )

    def summary(self, args: ReadSourceDocument.Args) -> str:
        return f"read source document {args.path}"

    async def run(self, args: ReadSourceDocument.Args, context: ToolContext) -> ToolResult:
        try:
            file = image_path(context, args.path)
            if not file.is_file():
                return ToolResult(ok=False, content=f"No file at {args.path}.")
            if file.stat().st_size > MAX_BYTES:
                return ToolResult(
                    ok=False, content=f"{args.path} is larger than {MAX_BYTES // (1024 * 1024)} MB."
                )
            digest = await asyncio.to_thread(read_source, file.name, file.read_bytes())
        except (SourceError, ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        return ToolResult(ok=True, content=describe_digest(digest, args.max_chars))


def source_tools() -> list[Tool]:
    return [ReadSourceDocument()]
