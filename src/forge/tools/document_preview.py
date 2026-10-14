"""One preview and one critic for every document format (TODO W4, D-345): preview_file and critique_document.

Word, Excel and PDF are turned into a PDF (Word, Excel or LibreOffice does the printing) and the PDF is rendered to page pictures; PowerPoint
uses its own slide export. A contact sheet puts many pages in one picture so the flow and consistency can be judged in one look."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from pydantic import Field

from forge.documents.preview import PreviewUnavailable
from forge.documents.preview import to_pdf as word_to_pdf
from forge.errors import ForgeError
from forge.llm.base import ChatRequest, Message
from forge.sheets import excel
from forge.slides import preview as slide_preview
from forge.slides.contact_sheet import ContactSheetUnavailable, make_contact_sheets
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.vision import _relative, _scratch, image_path
from forge.vision import images
from forge.vision import pdf as pdf_render

MAX_BYTES = 200 * 1024 * 1024
MAX_PAGES_SHOWN = 12
SUFFIXES = (".docx", ".xlsx", ".pptx", ".pdf")

CRITIC_RUBRIC = (
    "You are a strict reviewer of finished business documents, looking at a contact sheet of numbered pages (a Word document, a workbook "
    "printed by Excel, a PDF or a presentation). Judge only what you can see. Score each from 1 (poor) to 5 (excellent) and name the pages: "
    "hierarchy (a clear title, headings that stand out, an obvious reading order); consistency (the same fonts, sizes, colours, margins and "
    "alignment on every page); readability (text size, line length, contrast, enough white space, no crowding); tables and charts "
    "(readable, labelled, header row visible, nothing cut off, numbers aligned); completeness (nothing clipped, overlapping, empty or "
    "obviously unfinished, no leftover template text). Reply with JSON only: "
    '{"scores": {"hierarchy": n, "consistency": n, "readability": n, "tables_and_charts": n, "completeness": n}, '
    '"issues": [{"page": n, "severity": "high|medium|low", "problem": "...", "fix": "..."}], "verdict": "ship|fix_first", "summary": "..."}. '
    "Do not praise; do not invent problems; an empty issues list is fine when the pages are good."
)


class PreviewFailed(ForgeError):
    """No pictures could be made; the message says why."""


def _pictures(
    context: ToolContext, args_path: str, pages: list[int] | None, dpi: int
) -> tuple[list[Path], int, Path]:
    """(page pictures, total pages, the pdf made for them). Blocking: run in a thread."""
    source = image_path(context, args_path)
    if source.suffix.lower() not in SUFFIXES:
        raise PreviewFailed("Only .docx, .xlsx, .pptx and .pdf files can be previewed.")
    if not source.is_file():
        raise PreviewFailed(f"No file at {args_path}.")
    if source.stat().st_size > MAX_BYTES:
        raise PreviewFailed(f"{args_path} is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    folder = _scratch(context)
    kind = source.suffix.lower()
    if kind == ".pptx":
        if not slide_preview.available():
            raise PreviewFailed("PowerPoint is not installed here, so the slides cannot be shown.")
        try:
            made = slide_preview.export_slides(source, folder / f"{source.stem}-slides")
        except slide_preview.PreviewUnavailable as error:
            raise PreviewFailed(str(error)) from error
        chosen = [
            made[n - 1]
            for n in (pages or range(1, min(len(made), MAX_PAGES_SHOWN) + 1))
            if 1 <= n <= len(made)
        ]
        return chosen, len(made), source
    data = source.read_bytes()
    try:
        if kind == ".docx":
            pdf_bytes = word_to_pdf(data, ".docx")
        elif kind == ".xlsx":
            pdf_bytes = excel.to_pdf(data)
        else:
            pdf_bytes = data
    except (PreviewUnavailable, excel.ExcelUnavailable) as error:
        raise PreviewFailed(str(error)) from error
    target = folder / f"{source.stem}-preview.pdf"
    target.write_bytes(pdf_bytes)  # a scratch file in the jail-checked folder, like pdf_render's pictures
    count = pdf_render.page_count(target)
    wanted = pages or list(range(1, min(count, MAX_PAGES_SHOWN) + 1))
    return pdf_render.render(target, folder, wanted, dpi), count, target


def _sheets(pictures: list[Path], folder: Path, prefix: str) -> list[Path]:
    if len(pictures) < 2:
        return []
    try:
        return make_contact_sheets(pictures, folder, prefix=prefix)
    except ContactSheetUnavailable:
        return []


class PreviewFile(Tool):
    name = "preview_file"
    read_only = False
    description = (
        "Show a Word, Excel, PowerPoint or PDF file as pictures of its pages (Word, Excel or PowerPoint prints them; LibreOffice is the fallback "
        "for Word), plus one contact sheet of all the pages, so you can look at the layout with view_image: page breaks, tables, charts, "
        "headers and footers, consistency. Can also save a Word or Excel file as a PDF."
    )

    class Args(ToolArgs):
        path: str = Field(description="The .docx, .xlsx, .pptx or .pdf file")
        pages: list[int] | None = Field(
            default=None, description="Pages to render (1-based); empty = the first 12"
        )
        dpi: int = Field(default=100, ge=60, le=200)
        pdf_output: str = Field(
            default="",
            description="Also save the printed PDF here (Word and Excel files), e.g. docs/report.pdf",
        )

    def summary(self, args: PreviewFile.Args) -> str:
        return f"preview {args.path}"

    async def run(self, args: PreviewFile.Args, context: ToolContext) -> ToolResult:
        if args.pdf_output and not args.pdf_output.lower().endswith(".pdf"):
            return ToolResult(ok=False, content="pdf_output must end in .pdf")
        try:
            pictures, count, printed = await asyncio.to_thread(
                _pictures, context, args.path, args.pages, args.dpi
            )
            if args.pdf_output and printed.suffix.lower() == ".pdf":
                context.workspace.write_bytes(
                    args.pdf_output, printed.read_bytes(), f"{args.path} saved as PDF"
                )
            sheets = await asyncio.to_thread(
                _sheets, pictures, _scratch(context), f"{Path(args.path).stem}-contact"
            )
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(
                ok=False,
                content=f"{error} Use the read and check tools instead, and say that the layout was not looked at.",
            )
        listing = "\n".join(_relative(context, p) for p in pictures)
        extra = "\nContact sheet(s): " + ", ".join(_relative(context, s) for s in sheets) if sheets else ""
        return ToolResult(
            ok=True,
            content=f"{count} page(s); rendered {len(pictures)}. Look at them with view_image:\n{listing}{extra}",
        )


class CritiqueDocument(Tool):
    name = "critique_document"
    read_only = False
    description = (
        "An independent review of how a finished Word, Excel, PowerPoint or PDF file looks: the pages are printed, put on a contact sheet and "
        "judged by the vision model for hierarchy, consistency, readability, tables and charts, and completeness. Returns scores, issues with the "
        "page and a fix, and a verdict (ship or fix_first). Fix the high and medium issues, then run it again (at most three rounds)."
    )

    class Args(ToolArgs):
        path: str = Field(description="The .docx, .xlsx, .pptx or .pdf file")
        purpose: str = Field(default="", description="What the document is for and who reads it, in one line")

    def summary(self, args: CritiqueDocument.Args) -> str:
        return f"critique {args.path}"

    async def run(self, args: CritiqueDocument.Args, context: ToolContext) -> ToolResult:
        if context.router is None:
            return ToolResult(ok=False, content="No model is available to look at pages here.")
        try:
            pictures, count, _ = await asyncio.to_thread(_pictures, context, args.path, None, 90)
            folder = _scratch(context)
            sheets = await asyncio.to_thread(_sheets, pictures, folder, f"{Path(args.path).stem}-critic")
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(
                ok=False, content=f"{error} The file could not be looked at, so it cannot be reviewed."
            )
        shown = (sheets or pictures)[:3]
        urls = []
        for picture in shown:
            url, _ = images.for_model(images.open_image(picture))
            urls.append(url)
        question = f"The file has {count} page(s); the sheet(s) show the first {len(pictures)}. " + (
            f"Purpose: {args.purpose}" if args.purpose else ""
        )
        response = await context.router.chat(
            "vision",
            ChatRequest(
                messages=[Message.system(CRITIC_RUBRIC), Message(role="user", content=question, images=urls)]
            ),
        )
        text = response.text.strip()
        match = re.search(r"\{.*\}", text, re.S)
        try:
            parsed = json.loads(match.group(0)) if match else None
        except ValueError:
            parsed = None
        if parsed is None:
            return ToolResult(
                ok=True,
                content="The reviewer's answer could not be read as a list of scores; its words:\n"
                + text[:1500],
            )
        return ToolResult(ok=True, content=json.dumps(parsed, indent=2)[:4000])


def document_preview_tools() -> list[Tool]:
    return [PreviewFile(), CritiqueDocument()]
