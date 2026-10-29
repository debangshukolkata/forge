"""Sheet titles (D-543): a sheet with a `title` gets it in row 1, its `subtitle` in row 2 and the table from row 4.

The model keeps writing every address of the outline as if the header were row 1 (formulas, chart ranges, validations, the
freeze cell, notes, names); the builder moves the titled sheet's content down and rewrites those addresses here, so a title
never breaks a formula. Whole-column references (A:A) are left alone: they already cover every row."""

from __future__ import annotations

import re
from typing import Any

from forge.sheets.spec import SheetSpec, WorkbookSpec

TITLE_ROWS = 3  # title, subtitle, one empty row
CELL = re.compile(r"(\$?)([A-Za-z]{1,3})(\$?)(\d+)")
WHOLE_ROW = re.compile(r"(\$?)(\d+)")


def offsets(spec: WorkbookSpec) -> dict[str, int]:
    """How far each sheet's content moves down: TITLE_ROWS for a titled sheet, nothing for the others."""
    return {sheet.name: TITLE_ROWS for sheet in spec.sheets if sheet.title}


def _shift_side(side: str, offset: int) -> str:
    cell = CELL.fullmatch(side)
    if cell:
        return f"{cell.group(1)}{cell.group(2)}{cell.group(3)}{int(cell.group(4)) + offset}"
    row = WHOLE_ROW.fullmatch(side)
    if row:
        return f"{row.group(1)}{int(row.group(2)) + offset}"
    return side  # a whole column, or a name


def shift_range(reference: str, moved: dict[str, int], here: str) -> str:
    """One reference such as B2, $B$2:$D$13, Tasks!C2:C11 or 'My sheet'!A1, moved with the sheet it points into."""
    sheet, mark, address = reference.rpartition("!")
    target = sheet.strip("'").replace("''", "'") if mark else here
    offset = moved.get(target, 0)
    if not offset:
        return reference
    parts = address.split(":")
    if not all(
        CELL.fullmatch(part) or WHOLE_ROW.fullmatch(part) or re.fullmatch(r"\$?[A-Za-z]{1,3}", part)
        for part in parts
    ):
        return reference  # a defined name or something else that is not an address
    return sheet + mark + ":".join(_shift_side(part, offset) for part in parts)


def shift_formula(text: str, moved: dict[str, int], here: str) -> str:
    """Every cell reference of a formula moved with the sheet it points into; text in quotes and names stay."""
    from openpyxl.formula.tokenizer import Token, Tokenizer

    tokens = Tokenizer(text)
    for token in tokens.items:
        if token.type == Token.OPERAND and token.subtype == Token.RANGE:
            token.value = shift_range(token.value, moved, here)
    return str(tokens.render())


def _shift_value(value: Any, moved: dict[str, int], here: str) -> Any:
    return shift_formula(value, moved, here) if isinstance(value, str) and value.startswith("=") else value


def _shift_sheet(sheet: SheetSpec, moved: dict[str, int]) -> SheetSpec:
    here = sheet.name

    def address(reference: str | None) -> str | None:
        return shift_range(reference, moved, here) if reference else reference

    def addresses(references: str) -> str:
        return " ".join(shift_range(part, moved, here) for part in references.split())  # "A2:A9 C2:C9"

    return sheet.model_copy(
        update={
            "rows": [[_shift_value(value, moved, here) for value in row] for row in sheet.rows],
            "freeze": address(sheet.freeze),
            "validations": [v.model_copy(update={"range": addresses(v.range)}) for v in sheet.validations],
            "conditional": [
                c.model_copy(
                    update={
                        "range": addresses(c.range),
                        "value": _shift_value(c.value, moved, here),
                        "value2": _shift_value(c.value2, moved, here),
                    }
                )
                for c in sheet.conditional
            ],
            "charts": [
                c.model_copy(
                    update={
                        "data": address(c.data),
                        "categories": address(c.categories),
                        "anchor": address(c.anchor),
                    }
                )
                for c in sheet.charts
            ],
            "notes": {address(cell) or cell: text for cell, text in sheet.notes.items()},
        }
    )


def moved_spec(spec: WorkbookSpec) -> WorkbookSpec:
    """The outline with every address moved below the titles; unchanged when no sheet has a title."""
    moved = offsets(spec)
    if not moved:
        return spec
    first = spec.sheets[0].name if spec.sheets else ""
    return spec.model_copy(
        update={
            "sheets": [_shift_sheet(sheet, moved) for sheet in spec.sheets],
            # A name's target always names its sheet; the first sheet stands in for a bare address.
            "names": {
                name: shift_formula("=" + target, moved, first)[1:] for name, target in spec.names.items()
            },
        }
    )
