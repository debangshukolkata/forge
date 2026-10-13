"""Change an existing workbook and keep its formulas (D-339).

openpyxl drops charts, pictures and macros when it saves a workbook it loaded. `edit_workbook` therefore refuses a workbook that has any of
them unless the caller says the loss is fine (`allow_loss`), and the message names what would be lost. Formulas stay formulas: a cell is
only given a value when the operation says so."""

from __future__ import annotations

import io
from typing import Any, Literal

from pydantic import BaseModel, Field

from forge.sheets.build import INVALID_TITLE
from forge.sheets.read import open_workbook, package_extras
from forge.sheets.spec import WorkbookError


class Operation(BaseModel):
    op: Literal[
        "set_cells",
        "append_rows",
        "format",
        "add_sheet",
        "delete_sheet",
        "rename_sheet",
        "define_name",
        "column_width",
    ]
    sheet: str = ""
    cells: dict[str, Any] = Field(default_factory=dict, description="set_cells: {'B2': 12, 'C2': '=B2*2'}")
    rows: list[list[Any]] = Field(
        default_factory=list, description="append_rows: rows to add under the last used row"
    )
    range: str = ""
    number_format: str | None = None
    bold: bool | None = None
    fill: str | None = None
    name: str = ""
    target: str = ""
    width: float | None = None


def _sheet(workbook: Any, name: str) -> Any:
    if name not in workbook.sheetnames:
        raise WorkbookError(f"No sheet called '{name}'. Sheets: {', '.join(workbook.sheetnames)}")
    return workbook[name]


def _apply(workbook: Any, operation: Operation) -> str:
    from openpyxl.styles import Font, PatternFill
    from openpyxl.workbook.defined_name import DefinedName

    kind = operation.op
    if kind == "add_sheet":
        if not operation.name or len(operation.name) > 31 or INVALID_TITLE.search(operation.name):
            raise WorkbookError(f"Sheet name {operation.name!r}: 1 to 31 characters, none of [ ] : * ? / \\")
        if operation.name in workbook.sheetnames:
            raise WorkbookError(f"A sheet called '{operation.name}' exists already")
        workbook.create_sheet(operation.name)
        return f"added sheet '{operation.name}'"
    if kind == "define_name":
        if not operation.name or not operation.target:
            raise WorkbookError("define_name needs name and target (e.g. Assumptions!$B$2)")
        workbook.defined_names[operation.name] = DefinedName(operation.name, attr_text=operation.target)
        return f"named range {operation.name} -> {operation.target}"
    sheet = _sheet(workbook, operation.sheet)
    if kind == "delete_sheet":
        if len(workbook.sheetnames) == 1:
            raise WorkbookError("A workbook needs at least one sheet")
        workbook.remove(sheet)
        return f"deleted sheet '{operation.sheet}' (formulas elsewhere that referred to it now show #REF!; run check_workbook)"
    if kind == "rename_sheet":
        if not operation.name or len(operation.name) > 31 or INVALID_TITLE.search(operation.name):
            raise WorkbookError(f"Sheet name {operation.name!r} is not allowed")
        sheet.title = operation.name
        return f"renamed '{operation.sheet}' to '{operation.name}' (formulas in other sheets are NOT updated: check them)"
    if kind == "set_cells":
        for reference, value in operation.cells.items():
            sheet[reference] = value
        return f"set {len(operation.cells)} cell(s) on '{operation.sheet}'"
    if kind == "append_rows":
        for row in operation.rows:
            sheet.append(row)
        return f"appended {len(operation.rows)} row(s) to '{operation.sheet}'"
    if kind == "column_width":
        if not operation.range or operation.width is None:
            raise WorkbookError("column_width needs range (a column letter such as B) and width")
        sheet.column_dimensions[operation.range].width = operation.width
        return f"column {operation.range} width {operation.width}"
    if kind == "format":
        if not operation.range:
            raise WorkbookError("format needs range, e.g. B2:B20")
        cells = sheet[operation.range]
        flat = (
            [c for row in cells for c in row]
            if isinstance(cells, tuple) and cells and isinstance(cells[0], tuple)
            else (list(cells) if isinstance(cells, tuple) else [cells])
        )
        for cell in flat:
            if operation.number_format:
                cell.number_format = operation.number_format
            if operation.bold is not None:
                cell.font = Font(bold=operation.bold, color=cell.font.color)
            if operation.fill:
                cell.fill = PatternFill(
                    start_color=operation.fill, end_color=operation.fill, fill_type="solid"
                )
        return f"formatted {len(flat)} cell(s) in {operation.range}"
    raise WorkbookError(f"Unknown operation {kind}")


def edit_workbook(
    data: bytes, operations: list[Operation], allow_loss: bool = False
) -> tuple[bytes, list[str]]:
    charts, pictures, macros = package_extras(data)
    lost = [
        text
        for text, count in (
            (f"{charts} chart(s)", charts),
            (f"{pictures} picture(s)", pictures),
            ("macros", macros),
        )
        if count
    ]
    if lost and not allow_loss:
        raise WorkbookError(
            "This workbook has "
            + " and ".join(lost)
            + ", which the library used for editing would drop when saving. Ask the user whether losing them is fine, "
            "then call again with allow_loss=true; or make the change in a copy built from an outline (build_workbook)."
        )
    workbook = open_workbook(data)
    done = []
    for operation in operations:
        done.append(_apply(workbook, operation))
    if lost:
        done.append("LOST on save: " + " and ".join(lost))
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue(), done
