"""Word document tools (TODO W1, D-342): build_document, read_document, edit_document, check_document."""

from __future__ import annotations

import asyncio

from pydantic import Field

from forge.documents.build import build_document
from forge.documents.check import check_document, describe_problems
from forge.documents.edit import Operation, edit_document
from forge.documents.preview import PreviewUnavailable, to_pdf
from forge.documents.read import describe_document, read_document
from forge.documents.spec import DocumentError, parse_document
from forge.errors import ForgeError
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.vision import _relative, _scratch, image_path
from forge.vision import pdf as pdf_render

MAX_BYTES = 60 * 1024 * 1024


def _read(context: ToolContext, path: str) -> bytes:
    file = image_path(context, path)
    if not file.is_file():
        raise DocumentError(f"No file at {path}.")
    if file.stat().st_size > MAX_BYTES:
        raise DocumentError(f"{path} is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    return file.read_bytes()


class BuildDocument(Tool):
    name = "build_document"
    read_only = False
    description = (
        "Make a Word document (.docx) from an outline file you wrote (JSON or YAML; load the `make-document` skill for its format): "
        "headings, paragraphs with bold/italic/links, bullet and numbered lists, tables with a repeating header row, pictures with alt text, "
        "quotes, page breaks, a table of contents, header, footer and page numbers; optionally on a company template (.docx/.dotx). "
        "Returns the structure and accessibility problems it finds; fix them and build again."
    )

    class Args(ToolArgs):
        outline: str = Field(description="Path of the JSON or YAML outline, relative to the repository root")
        output: str = Field(description="Path of the .docx to write, e.g. docs/report.docx")
        reason: str = Field(default="", description="One line saying why; shown to the user in CHANGES.md.")

    def summary(self, args: BuildDocument.Args) -> str:
        return f"build document {args.output}"

    async def run(self, args: BuildDocument.Args, context: ToolContext) -> ToolResult:
        if not args.output.lower().endswith(".docx"):
            return ToolResult(ok=False, content="The output file name must end in .docx")
        outline = context.workspace.path_of(args.outline)
        if not outline.is_file():
            return ToolResult(ok=False, content=f"No outline file at {args.outline}. Write it first.")
        try:
            spec = parse_document(
                outline.read_text(encoding="utf-8"), as_yaml=outline.suffix.lower() in {".yaml", ".yml"}
            )
            template = _read(context, spec.template) if spec.template else None
            data = await asyncio.to_thread(
                build_document, spec, lambda name: image_path(context, name).read_bytes(), template
            )
            context.workspace.write_bytes(args.output, data, args.reason or "document built from an outline")
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        context.last_edit_step = context.step
        return ToolResult(
            ok=True,
            content=f"Wrote {args.output}.\n{describe_problems(await asyncio.to_thread(check_document, data))}",
        )


class ReadDocument(Tool):
    name = "read_document"
    read_only = True
    description = (
        "Read a Word document (.docx) as Markdown (headings, lists, tables) with its comments, the number of tracked changes and whether "
        "pictures have alt text."
    )

    class Args(ToolArgs):
        path: str = Field(description="The .docx file")
        max_chars: int = Field(default=12000, ge=1000, le=60000)

    def summary(self, args: ReadDocument.Args) -> str:
        return f"read document {args.path}"

    async def run(self, args: ReadDocument.Args, context: ToolContext) -> ToolResult:
        try:
            info = await asyncio.to_thread(read_document, _read(context, args.path))
        except (ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        return ToolResult(ok=True, content=describe_document(info, args.path, args.max_chars))


class EditDocument(Tool):
    name = "edit_document"
    read_only = False
    description = (
        "Change an existing Word document and keep its formatting: replace text (also text Word split across runs, in tables, headers and "
        "footers), set or delete a paragraph by its number (as read_document lists non-empty paragraphs), append a paragraph, add a comment. "
        "Run check_document afterwards."
    )

    class Args(ToolArgs):
        path: str = Field(description="The document to change")
        operations: list[Operation]
        output: str = Field(
            default="", description="Where to write the result; empty = change the file in place"
        )
        reason: str = Field(default="", description="One line saying why; shown to the user in CHANGES.md.")

    def summary(self, args: EditDocument.Args) -> str:
        return f"edit document {args.path}"

    async def run(self, args: EditDocument.Args, context: ToolContext) -> ToolResult:
        target = args.output or args.path
        if not target.lower().endswith(".docx"):
            return ToolResult(ok=False, content="The result must be a .docx file (macros are not kept).")
        try:
            edited, done = await asyncio.to_thread(edit_document, _read(context, args.path), args.operations)
            context.workspace.write_bytes(target, edited, args.reason or "document edited")
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        context.last_edit_step = context.step
        return ToolResult(ok=True, content="\n".join(done) + "\n" + describe_problems(check_document(edited)))


class CheckDocument(Tool):
    name = "check_document"
    read_only = True
    description = (
        "Check a Word document's structure and accessibility: title and language set, heading order, pictures without alt text, headings faked "
        "with bold text, empty-paragraph spacing, tables without a header row."
    )

    class Args(ToolArgs):
        path: str = Field(description="The document to check")

    def summary(self, args: CheckDocument.Args) -> str:
        return f"check document {args.path}"

    async def run(self, args: CheckDocument.Args, context: ToolContext) -> ToolResult:
        try:
            problems = await asyncio.to_thread(check_document, _read(context, args.path))
        except (ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        return ToolResult(ok=True, content=describe_problems(problems))


class PreviewDocument(Tool):
    name = "preview_document"
    read_only = False
    description = (
        "Show a Word document as pictures of its pages, made by Word itself (or LibreOffice when Word is missing), so you can look at the layout "
        "with view_image: page breaks, tables, pictures, headers and footers, the contents list. Can also save the document as a PDF."
    )

    class Args(ToolArgs):
        path: str = Field(description="The .docx file")
        pages: list[int] | None = Field(
            default=None, description="Pages to render (1-based); empty = all, at most 12"
        )
        dpi: int = Field(default=100, ge=60, le=200)
        pdf_output: str = Field(default="", description="Also write the PDF here, e.g. docs/report.pdf")

    def summary(self, args: PreviewDocument.Args) -> str:
        return f"preview document {args.path}"

    async def run(self, args: PreviewDocument.Args, context: ToolContext) -> ToolResult:
        if args.pdf_output and not args.pdf_output.lower().endswith(".pdf"):
            return ToolResult(ok=False, content="pdf_output must end in .pdf")
        try:
            source = image_path(context, args.path)
            data = _read(context, args.path)
            pdf_bytes = await asyncio.to_thread(to_pdf, data, source.suffix.lower() or ".docx")
            if args.pdf_output:
                context.workspace.write_bytes(args.pdf_output, pdf_bytes, f"{args.path} saved as PDF")
            folder = _scratch(context)
            temporary = folder / f"{source.stem}-preview.pdf"
            temporary.write_bytes(
                pdf_bytes
            )  # a scratch file in the jail-checked folder, like pdf_render's pictures
            count = pdf_render.page_count(temporary)
            wanted = args.pages or list(range(1, min(count, 12) + 1))
            written = await asyncio.to_thread(pdf_render.render, temporary, folder, wanted, args.dpi)
        except PreviewUnavailable as error:
            return ToolResult(
                ok=False,
                content=f"{error} Use check_document and read_document instead, and say the layout was not looked at.",
            )
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        listing = "\n".join(_relative(context, p) for p in written)
        done = f"{count} page(s); rendered {len(written)}. Look at them with view_image:"
        return ToolResult(ok=True, content=f"{done}\n{listing}")


def document_tools() -> list[Tool]:
    return [BuildDocument(), ReadDocument(), EditDocument(), CheckDocument(), PreviewDocument()]
