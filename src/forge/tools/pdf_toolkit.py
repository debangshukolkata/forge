"""PDF toolkit tools (TODO W3, D-343): read_pdf, edit_pdf, split_pdf, extract_pdf_images, build_pdf."""

from __future__ import annotations

import asyncio

from pydantic import Field

from forge.errors import ForgeError
from forge.pdfs.build import build_pdf_any, parse_pdf_spec
from forge.pdfs.edit import Operation, apply, extract_images, split_pdf
from forge.pdfs.read import PdfError, describe_pdf, read_pdf
from forge.pdfs.redact import PATTERNS, redact
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.brand_file import BRAND_FILE_DESCRIPTION, load_brand_file
from forge.tools.vision import image_path

MAX_BYTES = 200 * 1024 * 1024


def _read(context: ToolContext, path: str) -> bytes:
    file = image_path(context, path)
    if not file.is_file():
        raise PdfError(f"No file at {path}.")
    if file.stat().st_size > MAX_BYTES:
        raise PdfError(f"{path} is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    return file.read_bytes()


class ReadPdf(Tool):
    name = "read_pdf"
    read_only = True
    description = (
        "Read a PDF: text of each page in reading layout (columns and tables keep their alignment), title, author, form fields with values, "
        "number of pictures, and warnings (scanned with no text layer, JavaScript or embedded files). A protected PDF needs the password the "
        "user gave you."
    )

    class Args(ToolArgs):
        path: str
        password: str = Field(default="", description="Only a password the user gave for this file")
        max_chars: int = Field(default=12000, ge=1000, le=60000)

    def summary(self, args: ReadPdf.Args) -> str:
        return f"read pdf {args.path}"

    async def run(self, args: ReadPdf.Args, context: ToolContext) -> ToolResult:
        try:
            info = await asyncio.to_thread(read_pdf, _read(context, args.path), args.password)
        except (ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        return ToolResult(ok=True, content=describe_pdf(info, args.path, args.max_chars))


class EditPdf(Tool):
    name = "edit_pdf"
    read_only = False
    description = (
        "Change a PDF into a new file (the original is not touched): merge more PDFs onto it, rotate, crop, delete or extract pages, stamp a "
        "diagonal watermark or page numbers, fill form fields, set title/author, encrypt with a password, decrypt with the password the user gave. "
        "Operations run in order."
    )

    class Args(ToolArgs):
        path: str
        output: str = Field(description="Path of the new .pdf")
        operations: list[Operation]
        reason: str = Field(default="", description="One line saying why; shown to the user in CHANGES.md.")

    def summary(self, args: EditPdf.Args) -> str:
        return f"edit pdf {args.path} -> {args.output}"

    async def run(self, args: EditPdf.Args, context: ToolContext) -> ToolResult:
        if not args.output.lower().endswith(".pdf"):
            return ToolResult(ok=False, content="The output file name must end in .pdf")
        try:
            data = _read(context, args.path)

            def work() -> bytes:
                result = data
                for operation in args.operations:
                    result = apply(result, operation, lambda name: _read(context, name))
                return result

            result = await asyncio.to_thread(work)
            context.workspace.write_bytes(args.output, result, args.reason or "pdf edited")
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        context.last_edit_step = context.step
        return ToolResult(ok=True, content=f"Wrote {args.output} after {len(args.operations)} operation(s).")


class SplitPdf(Tool):
    name = "split_pdf"
    read_only = False
    description = "Split a PDF into several new PDFs, one per page range such as '1-3' and '4-6'."

    class Args(ToolArgs):
        path: str
        ranges: list[str]
        output_prefix: str = Field(description="Files are written as <prefix>-1.pdf, <prefix>-2.pdf ...")
        password: str = ""

    def summary(self, args: SplitPdf.Args) -> str:
        return f"split pdf {args.path}"

    async def run(self, args: SplitPdf.Args, context: ToolContext) -> ToolResult:
        try:
            parts = await asyncio.to_thread(split_pdf, _read(context, args.path), args.ranges, args.password)
            written = []
            for number, part in enumerate(parts, start=1):
                target = f"{args.output_prefix}-{number}.pdf"
                context.workspace.write_bytes(target, part, f"split from {args.path}")
                written.append(target)
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        return ToolResult(ok=True, content="Wrote " + ", ".join(written))


class ExtractPdfImages(Tool):
    name = "extract_pdf_images"
    read_only = False
    description = "Save the pictures inside a PDF as files in a folder (at most 60)."

    class Args(ToolArgs):
        path: str
        folder: str = Field(description="Folder to write them to, e.g. docs/pdf-images")
        password: str = ""

    def summary(self, args: ExtractPdfImages.Args) -> str:
        return f"extract images from {args.path}"

    async def run(self, args: ExtractPdfImages.Args, context: ToolContext) -> ToolResult:
        try:
            found = await asyncio.to_thread(extract_images, _read(context, args.path), args.password)
            for name, data in found:
                context.workspace.write_bytes(
                    f"{args.folder.rstrip('/')}/{name}", data, "picture extracted from a PDF"
                )
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        return ToolResult(
            ok=True,
            content=f"{len(found)} picture(s) saved in {args.folder}: " + ", ".join(n for n, _ in found[:20]),
        )


class BuildPdf(Tool):
    name = "build_pdf"
    read_only = False
    description = (
        "Create a PDF from an outline file (JSON or YAML; load the `pdf-toolkit` skill): title, headings, paragraphs (with a link), bullet and "
        "numbered lists, tables with a repeating header row, pictures with captions, page breaks, footer and page numbers. For a document the "
        "user will edit, make a Word file instead and convert."
    )

    class Args(ToolArgs):
        outline: str = Field(description="Path of the JSON or YAML outline")
        output: str = Field(description="Path of the .pdf to write")
        brand_file: str = Field(default="", description=BRAND_FILE_DESCRIPTION)
        reason: str = Field(default="", description="One line saying why; shown to the user in CHANGES.md.")

    def summary(self, args: BuildPdf.Args) -> str:
        return f"build pdf {args.output}"

    async def run(self, args: BuildPdf.Args, context: ToolContext) -> ToolResult:
        if not args.output.lower().endswith(".pdf"):
            return ToolResult(ok=False, content="The output file name must end in .pdf")
        outline = context.workspace.path_of(args.outline)
        if not outline.is_file():
            return ToolResult(ok=False, content=f"No outline file at {args.outline}. Write it first.")
        try:
            spec = parse_pdf_spec(
                outline.read_text(encoding="utf-8"), as_yaml=outline.suffix.lower() in {".yaml", ".yml"}
            )
            kit = load_brand_file(context, args.brand_file)
            if kit is not None:
                spec.brand = kit
            data, note = await asyncio.to_thread(
                build_pdf_any, spec, lambda name: image_path(context, name).read_bytes()
            )
            context.workspace.write_bytes(args.output, data, args.reason or "pdf built from an outline")
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        context.last_edit_step = context.step
        return ToolResult(
            ok=True,
            content=f"Wrote {args.output}. Render it with pdf_render and look at the pages."
            + (chr(10) + note if note else ""),
        )


class RedactRegion(ToolArgs):
    page: int = Field(ge=1, description="page number, from 1")
    left: float
    bottom: float
    right: float
    top: float


class RedactPdf(Tool):
    name = "redact_pdf"
    read_only = False
    description = (
        "Permanently remove text from a PDF into a NEW file (the original is not touched). Every page becomes a picture with the matches blacked out, "
        "so the text is really gone (a black box drawn over text leaves it selectable). Give exact `terms` (case-insensitive), named `patterns` "
        f"({', '.join(PATTERNS)}) and/or `regions` in PDF points. The result has no text layer or metadata; run ocr_pdf on it if it must be searchable. "
        "A scan has no text to search: give regions for it. Check the result with view_image before it leaves the project."
    )

    class Args(ToolArgs):
        path: str
        output: str = Field(description="Path of the new .pdf")
        terms: list[str] = Field(default_factory=list)
        patterns: list[str] = Field(default_factory=list)
        regions: list[RedactRegion] = Field(default_factory=list)
        password: str = ""
        reason: str = Field(default="", description="One line saying why; shown to the user in CHANGES.md.")

    def summary(self, args: RedactPdf.Args) -> str:
        return f"redact pdf {args.path} -> {args.output}"

    async def run(self, args: RedactPdf.Args, context: ToolContext) -> ToolResult:
        if not args.output.lower().endswith(".pdf"):
            return ToolResult(ok=False, content="The output file name must end in .pdf")
        regions = [(r.page, r.left, r.bottom, r.right, r.top) for r in args.regions]
        try:
            data = _read(context, args.path)
            result, report = await asyncio.to_thread(
                redact, data, args.terms, args.patterns, regions, 200, args.password
            )
            if report.boxes == 0:
                return ToolResult(
                    ok=False, content="Nothing matched, so no file was written." + chr(10) + report.summary()
                )
            context.workspace.write_bytes(args.output, result, args.reason or "pdf redacted")
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        context.last_edit_step = context.step
        warning = (
            (chr(10) + "WARNING: the result still has a text layer.")
            if report.text_left
            else (chr(10) + "Verified: the result has no text layer.")
        )
        return ToolResult(ok=True, content=f"Wrote {args.output}. {report.summary()}{warning}")


def pdf_toolkit_tools() -> list[Tool]:
    return [ReadPdf(), EditPdf(), SplitPdf(), ExtractPdfImages(), BuildPdf(), RedactPdf()]
