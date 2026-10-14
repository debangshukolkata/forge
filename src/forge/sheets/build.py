"""Build an .xlsx from a `WorkbookSpec` with openpyxl (D-339)."""

from __future__ import annotations

import importlib
import io
import re
from datetime import date
from typing import Any

from forge.brand.kit import Resolved
from forge.sheets.spec import ChartSpec, Conditional, SheetSpec, WorkbookError, WorkbookSpec

INVALID_TITLE = re.compile(r"[\[\]:*?/\\]")
HEADER_FILL = "1F3864"


def load_openpyxl() -> Any:
    try:
        return importlib.import_module("openpyxl")
    except ImportError as error:
        raise WorkbookError(
            "openpyxl is not installed: pip install openpyxl (the forge[docs] extra)"
        ) from error


def _check_names(spec: WorkbookSpec) -> None:
    seen: set[str] = set()
    for sheet in spec.sheets:
        if not sheet.name or len(sheet.name) > 31 or INVALID_TITLE.search(sheet.name):
            raise WorkbookError(f"Sheet name {sheet.name!r}: 1 to 31 characters, none of [ ] : * ? / \\")
        if sheet.name.lower() in seen:
            raise WorkbookError(f"Two sheets are called {sheet.name!r}")
        seen.add(sheet.name.lower())
    if not spec.sheets:
        raise WorkbookError("The workbook needs at least one sheet")


def _chart(sheet: Any, chart: ChartSpec) -> Any:
    from openpyxl.chart import AreaChart, BarChart, LineChart, PieChart, Reference, ScatterChart, Series

    data = sheet[chart.data]
    first, last = data[0][0], data[-1][-1]
    values = Reference(sheet, min_col=first.column, max_col=last.column, min_row=first.row, max_row=last.row)
    kinds: dict[str, Any] = {
        "column": BarChart,
        "bar": BarChart,
        "line": LineChart,
        "pie": PieChart,
        "area": AreaChart,
        "scatter": ScatterChart,
    }
    made = kinds[chart.type]()
    if chart.type == "bar":
        made.type = "bar"
    elif chart.type == "column":
        made.type = "col"
    made.title = chart.title or None
    if chart.type == "scatter":
        for column in range(first.column + 1, last.column + 1):
            xs = Reference(sheet, min_col=first.column, min_row=first.row + 1, max_row=last.row)
            ys = Reference(sheet, min_col=column, min_row=first.row, max_row=last.row)
            made.series.append(Series(ys, xs, title_from_data=True))
    else:
        made.add_data(values, titles_from_data=True)
        if chart.categories:
            cats = sheet[chart.categories]
            made.set_categories(
                Reference(
                    sheet,
                    min_col=cats[0][0].column,
                    max_col=cats[-1][-1].column,
                    min_row=cats[0][0].row,
                    max_row=cats[-1][-1].row,
                )
            )
    if chart.type != "pie":
        if chart.x_title:
            made.x_axis.title = chart.x_title
        if chart.y_title:
            made.y_axis.title = chart.y_title
        made.x_axis.delete = False  # recent openpyxl versions hide the axes unless told otherwise
        made.y_axis.delete = False
    made.width, made.height = 18, 9
    return made


def _conditional(sheet: Any, rule: Conditional) -> None:
    from openpyxl.formatting.rule import CellIsRule, ColorScaleRule, DataBarRule, FormulaRule
    from openpyxl.styles import Font, PatternFill

    fill = PatternFill(start_color=rule.fill, end_color=rule.fill, fill_type="solid")
    font = Font(color=rule.font) if rule.font else None
    first_cell = rule.range.split(":")[0].replace("$", "")
    made: Any
    if rule.rule == "color_scale":
        made = ColorScaleRule(
            start_type="min",
            start_color="F8696B",
            mid_type="percentile",
            mid_value=50,
            mid_color="FFEB84",
            end_type="max",
            end_color="63BE7B",
        )
    elif rule.rule == "data_bar":
        made = DataBarRule(start_type="min", end_type="max", color="5B9BD5")
    elif rule.rule == "text_contains":
        made = FormulaRule(formula=[f'ISNUMBER(SEARCH("{rule.value}",{first_cell}))'], fill=fill, font=font)
    else:
        operator = {
            "greater_than": "greaterThan",
            "less_than": "lessThan",
            "between": "between",
            "equal": "equal",
        }[rule.rule]
        formula = [str(rule.value)] + ([str(rule.value2)] if rule.rule == "between" else [])
        made = CellIsRule(operator=operator, formula=formula, fill=fill, font=font)
    sheet.conditional_formatting.add(rule.range, made)


def _build_sheet(workbook: Any, spec: SheetSpec, first: bool, brand: Resolved) -> None:
    from openpyxl.comments import Comment
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import column_index_from_string, get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.worksheet.table import Table, TableStyleInfo

    sheet = workbook.active if first else workbook.create_sheet()
    sheet.title = spec.name
    if spec.tab_colour:
        sheet.sheet_properties.tabColor = spec.tab_colour
    fill_colour = brand.header_fill or HEADER_FILL
    header_font = Font(bold=True, color=brand.header_text or "FFFFFF", name=brand.body_font)
    header_fill = PatternFill(start_color=fill_colour, end_color=fill_colour, fill_type="solid")
    for index, column in enumerate(spec.columns, start=1):
        cell = sheet.cell(row=1, column=index, value=column.header)
        if not spec.table:
            cell.font, cell.fill = header_font, header_fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        sheet.column_dimensions[get_column_letter(index)].width = column.width or max(
            10.0, min(40.0, len(column.header) + 4.0)
        )
    first_row = 2 if spec.columns else 1  # the header takes row 1 only when there is one
    for row_number, row in enumerate(spec.rows, start=first_row):
        for index, value in enumerate(row, start=1):
            if (
                isinstance(value, str)
                and index <= len(spec.columns)
                and "yy" in (spec.columns[index - 1].format or "")
                and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
            ):
                value = date.fromisoformat(value)  # a date column's ISO text becomes a real date
            cell = sheet.cell(row=row_number, column=index, value=value)
            if brand.body_font:
                cell.font = Font(name=brand.body_font, color=brand.text)
            if index <= len(spec.columns) and spec.columns[index - 1].format:
                cell.number_format = spec.columns[index - 1].format
    last_row = len(spec.rows) + first_row - 1
    if spec.total_row and spec.columns:
        total = last_row + 1
        for letter, what in spec.total_row.items():
            index = column_index_from_string(letter)
            if what.isupper() and what.isalpha():
                cell = sheet.cell(
                    row=total, column=index, value=f"={what}({letter}{first_row}:{letter}{last_row})"
                )
                if index <= len(spec.columns) and spec.columns[index - 1].format:
                    cell.number_format = spec.columns[index - 1].format
            else:
                cell = sheet.cell(row=total, column=index, value=what)
            cell.font = Font(bold=True)
    if spec.table and spec.columns and spec.rows:
        reference = f"A1:{get_column_letter(len(spec.columns))}{last_row}"
        table = Table(displayName=re.sub(r"\W", "_", spec.name)[:30] or "Table1", ref=reference)
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        sheet.add_table(table)
    if spec.freeze:
        sheet.freeze_panes = spec.freeze
    elif spec.columns:
        sheet.freeze_panes = "A2"
    for validation in spec.validations:
        if validation.choices:
            made = DataValidation(
                type="list", formula1='"' + ",".join(validation.choices) + '"', allow_blank=True
            )
        elif validation.whole:
            made = DataValidation(
                type="whole",
                operator="between",
                formula1=str(validation.whole[0]),
                formula2=str(validation.whole[1]),
            )
        elif validation.decimal:
            made = DataValidation(
                type="decimal",
                operator="between",
                formula1=str(validation.decimal[0]),
                formula2=str(validation.decimal[1]),
            )
        else:
            raise WorkbookError(f"Validation for {validation.range} needs choices, whole or decimal")
        if validation.message:
            made.error, made.errorTitle, made.showErrorMessage = validation.message, "Not allowed", True
        made.add(validation.range)
        sheet.add_data_validation(made)
    for rule in spec.conditional:
        _conditional(sheet, rule)
    for reference, text in spec.notes.items():
        sheet[reference].comment = Comment(text, "DebCraft")
    for chart in spec.charts:
        sheet.add_chart(_chart(sheet, chart), chart.anchor)


def build_workbook(spec: WorkbookSpec) -> bytes:
    openpyxl = load_openpyxl()
    _check_names(spec)
    workbook = openpyxl.Workbook()
    brand = Resolved(spec.brand)
    try:
        for index, sheet in enumerate(spec.sheets):
            _build_sheet(workbook, sheet, index == 0, brand)
        from openpyxl.workbook.defined_name import DefinedName

        for name, target in spec.names.items():
            workbook.defined_names[name] = DefinedName(name, attr_text=target)
        if spec.title:
            workbook.properties.title = spec.title
    except WorkbookError:
        raise
    except Exception as error:  # a bad range or format in the outline
        raise WorkbookError(
            f"The workbook could not be built: {type(error).__name__}: {str(error)[:300]}"
        ) from error
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()
