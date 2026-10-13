"""Read a workbook with its formulas and its last calculated values (D-339)."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from typing import Any

from forge.sheets.build import load_openpyxl
from forge.sheets.spec import WorkbookError

MAX_CELLS_PER_SHEET = 60
MAX_SHEETS = 20


@dataclass
class SheetInfo:
    name: str
    dimensions: str
    rows: int
    columns: int
    freeze: str | None
    tables: list[str]
    merged: list[str]
    formulas: int
    cells: list[str] = field(default_factory=list)  # "B2 = 12 (formula: =SUM(...))" for the first cells


@dataclass
class WorkbookInfo:
    sheets: list[SheetInfo]
    names: dict[str, str]
    charts: int
    pictures: int
    has_macros: bool
    calculated: bool  # False when no formula has a stored value (made by a library, never opened in Excel)


def package_extras(data: bytes) -> tuple[int, int, bool]:
    """(charts, pictures, macros) in the package; openpyxl would lose all three on a save."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile as error:
        raise WorkbookError("The file is not an Excel workbook (.xlsx is a zip package)") from error
    charts = sum(1 for n in names if n.startswith("xl/charts/chart") and n.endswith(".xml"))
    pictures = sum(1 for n in names if n.startswith("xl/media/"))
    return charts, pictures, any(n.endswith("vbaProject.bin") for n in names)


def open_workbook(data: bytes, values: bool = False) -> Any:
    openpyxl = load_openpyxl()
    try:
        return openpyxl.load_workbook(io.BytesIO(data), data_only=values)
    except Exception as error:
        raise WorkbookError(
            f"The workbook could not be read ({type(error).__name__}); a damaged or password-protected file?"
        ) from error


def read_workbook(data: bytes, max_cells: int = MAX_CELLS_PER_SHEET) -> WorkbookInfo:
    charts, pictures, macros = package_extras(data)
    formulas_book = open_workbook(data)
    values_book = open_workbook(data, values=True)
    sheets: list[SheetInfo] = []
    any_value = False
    total_formulas = 0
    for sheet in formulas_book.worksheets[:MAX_SHEETS]:
        stored = values_book[sheet.title]
        info = SheetInfo(
            sheet.title,
            sheet.dimensions,
            sheet.max_row,
            sheet.max_column,
            sheet.freeze_panes,
            list(sheet.tables.keys()),
            [str(r) for r in sheet.merged_cells.ranges][:10],
            0,
        )
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                is_formula = isinstance(cell.value, str) and cell.value.startswith("=")
                if is_formula:
                    info.formulas += 1
                    total_formulas += 1
                    if stored[cell.coordinate].value is not None:
                        any_value = True
                if len(info.cells) < max_cells:
                    shown = stored[cell.coordinate].value if is_formula else cell.value
                    text = f"{cell.coordinate} = {shown!r}"
                    if is_formula:
                        text += f"  (formula {cell.value})"
                    if cell.number_format and cell.number_format != "General":
                        text += f"  [{cell.number_format}]"
                    info.cells.append(text)
        sheets.append(info)
    names = {name: str(defined.attr_text) for name, defined in formulas_book.defined_names.items()}
    return WorkbookInfo(sheets, names, charts, pictures, macros, any_value or total_formulas == 0)


def describe_workbook(info: WorkbookInfo, name: str = "workbook") -> str:
    lines = [f"{name}: {len(info.sheets)} sheet(s), {info.charts} chart(s), {info.pictures} picture(s)"]
    if info.has_macros:
        lines.append("It contains macros (never run by DebCraft).")
    if info.names:
        lines.append("Named ranges: " + ", ".join(f"{k} -> {v}" for k, v in list(info.names.items())[:20]))
    if not info.calculated:
        lines.append(
            "No formula has a stored value: the file was never calculated (made by a library). Excel calculates on opening; "
            "check_workbook with recalculate=true gives the real values when Excel is installed."
        )
    for sheet in info.sheets:
        extra = []
        if sheet.freeze:
            extra.append(f"frozen at {sheet.freeze}")
        if sheet.tables:
            extra.append("tables " + ", ".join(sheet.tables))
        if sheet.merged:
            extra.append("merged " + ", ".join(sheet.merged))
        lines.append(
            f"\nSheet '{sheet.name}' {sheet.dimensions}: {sheet.rows} rows x {sheet.columns} columns, {sheet.formulas} formulas"
            + (f" ({'; '.join(extra)})" if extra else "")
        )
        lines += [f"  {c}" for c in sheet.cells]
    return "\n".join(lines)
