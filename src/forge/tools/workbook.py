"""Excel workbook tools (TODO W2, D-339): build_workbook, read_workbook, edit_workbook, check_workbook."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from pydantic import Field

from forge.errors import ForgeError
from forge.ooxml.validate import validate_package
from forge.sheets import excel
from forge.sheets.build import build_workbook
from forge.sheets.check import check_workbook, describe_findings
from forge.sheets.clean import clean_table, read_rows
from forge.sheets.edit import Operation, edit_workbook
from forge.sheets.read import describe_workbook, read_workbook
from forge.sheets.spec import WorkbookError, WorkbookSpec, parse_workbook
from forge.sheets.titles import TITLE_ROWS
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.tools.brand_file import BRAND_FILE_DESCRIPTION, load_brand_file
from forge.tools.vision import image_path

MAX_BYTES = 60 * 1024 * 1024


def _package_faults(faults: list[str]) -> str:
    if not faults:
        return ""
    return "\nPackage problems (Excel may offer to repair the file):\n" + "\n".join(
        f"  - {f}" for f in faults
    )


def _read(context: ToolContext, path: str) -> bytes:
    file = image_path(context, path)
    if not file.is_file():
        raise WorkbookError(f"No file at {path}.")
    if file.stat().st_size > MAX_BYTES:
        raise WorkbookError(f"{path} is larger than {MAX_BYTES // (1024 * 1024)} MB.")
    return file.read_bytes()


class BuildWorkbook(Tool):
    name = "build_workbook"
    read_only = False
    description = (
        "Make an Excel workbook (.xlsx) from an outline file you wrote (JSON or YAML; load the `make-spreadsheet` skill for its format). "
        "A cell value starting with '=' is a real formula. The outline can hold a title and subtitle per sheet, column formats and widths, an Excel table, frozen panes, a "
        "total row, named ranges, data validation, conditional formatting, cell notes and native charts. Always run check_workbook afterwards."
    )

    class Args(ToolArgs):
        outline: str = Field(description="Path of the JSON or YAML outline, relative to the repository root")
        output: str = Field(description="Path of the .xlsx to write, e.g. docs/budget.xlsx")
        brand_file: str = Field(default="", description=BRAND_FILE_DESCRIPTION)
        reason: str = Field(default="", description="One line saying why; shown to the user in CHANGES.md.")

    def summary(self, args: BuildWorkbook.Args) -> str:
        return f"build workbook {args.output}"

    async def run(self, args: BuildWorkbook.Args, context: ToolContext) -> ToolResult:
        if not args.output.lower().endswith(".xlsx"):
            return ToolResult(ok=False, content="The output file name must end in .xlsx")
        outline = context.workspace.path_of(args.outline)
        if not outline.is_file():
            return ToolResult(ok=False, content=f"No outline file at {args.outline}. Write it first.")
        try:
            spec = parse_workbook(
                outline.read_text(encoding="utf-8"), as_yaml=outline.suffix.lower() in {".yaml", ".yml"}
            )
            kit = load_brand_file(context, args.brand_file)
            if kit is not None:
                spec.brand = kit
            notes: list[str] = []
            data = await asyncio.to_thread(build_workbook, spec, notes)
            context.workspace.write_bytes(args.output, data, args.reason or "workbook built from an outline")
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        context.last_edit_step = context.step
        findings = check_workbook(data)
        faults = validate_package(data)
        return ToolResult(
            ok=True,
            content=f"Wrote {args.output}: {len(spec.sheets)} sheet(s), each printing one page wide.\n"
            + _title_lines(spec)
            + "".join(f"Note: {note}\n" for note in notes)
            + describe_findings(findings)
            + _package_faults(faults),
        )


def _title_lines(spec: WorkbookSpec) -> str:
    """Where titled tables landed (the addresses moved, D-543), and the sheets a reader meets without a title."""
    titled = [sheet.name for sheet in spec.sheets if sheet.title]
    untitled = [sheet.name for sheet in spec.sheets if not sheet.title and sheet.columns]
    lines = ""
    if titled:
        lines += (
            f"Titled: {', '.join(titled)}: title in row 1, header in row {1 + TITLE_ROWS}, data from row {2 + TITLE_ROWS}; "
            f"every address of the outline moved down {TITLE_ROWS} rows with it. Later edits use the real rows.\n"
        )
    if untitled:
        lines += f"No title: {', '.join(untitled)}. A sheet a person reads starts with a `title` (and `subtitle`) in the outline.\n"
    return lines


class ReadWorkbook(Tool):
    name = "read_workbook"
    read_only = True
    description = (
        "Read an Excel workbook: its sheets, tables, named ranges, frozen panes, and the first cells of each sheet with their formulas and "
        "last calculated values and number formats. Says when the file holds charts, pictures or macros."
    )

    class Args(ToolArgs):
        path: str = Field(description="The .xlsx or .xlsm file")
        max_cells: int = Field(default=60, ge=5, le=500, description="Cells to show per sheet")

    def summary(self, args: ReadWorkbook.Args) -> str:
        return f"read workbook {args.path}"

    async def run(self, args: ReadWorkbook.Args, context: ToolContext) -> ToolResult:
        try:
            data = _read(context, args.path)
            info = await asyncio.to_thread(read_workbook, data, args.max_cells)
        except (ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        return ToolResult(ok=True, content=describe_workbook(info, args.path))


class EditWorkbook(Tool):
    name = "edit_workbook"
    read_only = False
    description = (
        "Change an existing Excel workbook: set cells (a value or a '=formula'), append rows, format a range, add, rename or delete a sheet, "
        "define a named range, set a column width. Formulas stay formulas; charts and pictures are kept. If the save would drop something "
        "(macros, Excel's chart styling) the edit is refused and names it; set allow_loss only after the user said that loss is fine. "
        "Run check_workbook afterwards."
    )

    class Args(ToolArgs):
        path: str = Field(description="The workbook to change")
        operations: list[Operation]
        output: str = Field(
            default="", description="Where to write the result; empty = change the file in place"
        )
        allow_loss: bool = Field(
            default=False, description="Only after the user agreed: accept the loss the refusal named"
        )
        reason: str = Field(default="", description="One line saying why; shown to the user in CHANGES.md.")

    def summary(self, args: EditWorkbook.Args) -> str:
        return f"edit workbook {args.path}"

    async def run(self, args: EditWorkbook.Args, context: ToolContext) -> ToolResult:
        target = args.output or args.path
        if not target.lower().endswith(".xlsx"):
            return ToolResult(ok=False, content="The result must be an .xlsx file (macros are not kept).")
        try:
            data = _read(context, args.path)
            edited, done = await asyncio.to_thread(edit_workbook, data, args.operations, args.allow_loss)
            context.workspace.write_bytes(target, edited, args.reason or "workbook edited")
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        context.last_edit_step = context.step
        return ToolResult(ok=True, content="\n".join(done) + "\n" + describe_findings(check_workbook(edited)))


class CheckWorkbook(Tool):
    name = "check_workbook"
    read_only = False
    description = (
        "Check a workbook's formulas: error values, references to missing sheets, circular references, text where a number is expected, and "
        "numbers typed inside formulas. With recalculate=true and Excel installed (Windows), Excel itself calculates the file, the real errors "
        "are listed, and the calculated values are saved into the file so viewers that do not calculate show numbers."
    )

    class Args(ToolArgs):
        path: str = Field(description="The workbook to check")
        recalculate: bool = Field(
            default=False, description="Let Excel calculate it (when installed) and save the values"
        )

    def summary(self, args: CheckWorkbook.Args) -> str:
        return f"check workbook {args.path}"

    async def run(self, args: CheckWorkbook.Args, context: ToolContext) -> ToolResult:
        try:
            data = _read(context, args.path)
            text = describe_findings(await asyncio.to_thread(check_workbook, data))
            if args.recalculate:
                try:
                    errors, saved = await asyncio.to_thread(excel.recalculate, data)
                except excel.ExcelUnavailable as error:
                    return ToolResult(ok=True, content=f"{text}\nExcel check not done: {error}")
                text += "\nExcel calculated the workbook: " + (
                    "; ".join(f"{s}!{c} shows {t}" for s, c, t in errors[:40])
                    if errors
                    else "no cell shows an error."
                )
                if saved and args.path.lower().endswith(".xlsx") and not errors:
                    context.workspace.write_bytes(args.path, saved, "calculated values stored by Excel")
                    text += "\nThe calculated values are stored in the file."
        except (ForgeError, OSError) as error:
            return ToolResult(ok=False, content=str(error))
        return ToolResult(ok=True, content=text)


class CleanTable(Tool):
    name = "clean_table"
    read_only = False
    description = (
        "Turn a messy CSV, TSV or Excel sheet into a clean workbook: title lines above the header and a header over two rows are handled, blank rows and "
        "columns, duplicates and stray spaces removed, text such as '1,234.50', '(300)', '12%', '$1,200' turned into numbers with a number format, dates "
        "turned into real dates (day-first or month-first decided from the whole column, and said when it is a guess). Writes a clean .xlsx (an Excel "
        "table with a frozen header) and optionally the outline, and REPORTS every change and doubt: tell the user the report. Total lines are kept as data "
        "and flagged."
    )

    class Args(ToolArgs):
        path: str = Field(description="The messy .csv, .tsv, .txt or .xlsx file")
        output: str = Field(description="Path of the clean .xlsx to write")
        outline_output: str = Field(
            default="",
            description="Also save the outline (JSON) so it can be extended and built again with build_workbook",
        )
        sheet_name: str = Field(default="Data", max_length=31)
        reason: str = Field(default="", description="One line saying why; shown to the user in CHANGES.md.")

    def summary(self, args: CleanTable.Args) -> str:
        return f"clean table {args.path}"

    async def run(self, args: CleanTable.Args, context: ToolContext) -> ToolResult:
        if not args.output.lower().endswith(".xlsx"):
            return ToolResult(ok=False, content="The output file name must end in .xlsx")
        try:
            rows = await asyncio.to_thread(read_rows, _read(context, args.path), Path(args.path).name)
            result = await asyncio.to_thread(clean_table, rows)
            outline = result.outline(args.sheet_name)
            data = await asyncio.to_thread(build_workbook, WorkbookSpec.model_validate(outline))
            context.workspace.write_bytes(args.output, data, args.reason or f"cleaned from {args.path}")
            if args.outline_output:
                context.workspace.write_text(
                    args.outline_output,
                    json.dumps(outline, indent=1, default=str),
                    "outline of the cleaned table",
                )
        except (ForgeError, OSError, ValueError) as error:
            return ToolResult(ok=False, content=str(error))
        context.last_edit_step = context.step
        return ToolResult(
            ok=True,
            content=f"Wrote {args.output}: {len(result.rows)} row(s), {len(result.columns)} column(s).\nWhat was changed:\n"
            + "\n".join(f"  - {line}" for line in result.report),
        )


def workbook_tools() -> list[Tool]:
    return [BuildWorkbook(), ReadWorkbook(), EditWorkbook(), CheckWorkbook(), CleanTable()]
