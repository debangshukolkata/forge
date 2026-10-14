"""Inputs of a model are marked: a number that a formula depends on is styled as an input (blue font), the modelling convention that lets a reader see
what may be changed (D-355). `input_cells` finds them, `mark_inputs` styles them, `unmarked_inputs` reports the ones that are not styled."""

from __future__ import annotations

import re
from typing import Any

from forge.sheets.check import _references

INPUT_COLOUR = "0000FF"
NAME_TARGET = re.compile(r"^'?([^'!]+)'?!\$?([A-Z]{1,3})\$?(\d+)$")


def _column_number(letters: str) -> int:
    number = 0
    for char in letters:
        number = number * 26 + ord(char) - 64
    return number


def _named_cells(workbook: Any) -> dict[str, tuple[str, int, int]]:
    found: dict[str, tuple[str, int, int]] = {}
    for name, defined in workbook.defined_names.items():
        match = NAME_TARGET.match(str(defined.attr_text))
        if match:
            found[name.lower()] = (match.group(1), _column_number(match.group(2)), int(match.group(3)))
    return found


def input_cells(workbook: Any) -> set[tuple[str, int, int]]:
    """Numeric constants (not formulas) that at least one formula reads, directly or through a named cell."""
    names = _named_cells(workbook)
    read: set[tuple[str, int, int]] = set()
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    cells, _ = _references(cell.value, sheet.title, set())
                    read |= cells
                    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_.]*", cell.value):
                        if token.lower() in names:
                            read.add(names[token.lower()])
    inputs = set()
    for sheet_name, column, row in read:
        if sheet_name in workbook.sheetnames:
            value = workbook[sheet_name].cell(row=row, column=column).value
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                inputs.add((sheet_name, column, row))
    return inputs


def _is_marked(cell: Any) -> bool:
    colour = cell.font.color
    return bool(
        colour is not None and colour.rgb is not None and str(colour.rgb).upper().endswith(INPUT_COLOUR)
    )


def mark_inputs(workbook: Any) -> int:
    from copy import copy

    marked = 0
    for sheet_name, column, row in input_cells(workbook):
        cell = workbook[sheet_name].cell(row=row, column=column)
        if not _is_marked(cell):
            font = copy(cell.font)
            font.color = INPUT_COLOUR
            cell.font = font
            marked += 1
    return marked


def unmarked_inputs(workbook: Any) -> list[str]:
    return [
        f"{sheet}!{workbook[sheet].cell(row=row, column=column).coordinate}"
        for sheet, column, row in sorted(input_cells(workbook))
        if not _is_marked(workbook[sheet].cell(row=row, column=column))
    ]
