"""Find formula faults in a workbook without a spreadsheet program (D-339).

Finds: error values stored in cells (#REF!, #DIV/0!, #NAME?, #VALUE!, #N/A, #NUM!, #NULL!), error text written into a formula, references to sheets
that do not exist, circular references (cells that depend on themselves), and formulas that give text in a cell formatted as a number. Numbers
typed inside formulas ("=B2*1.2") are listed as a hint: put the rate in a cell with a label and use a named range. A calculation by Excel itself
(`excel.py`) is the final word; this check is what runs everywhere else."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from forge.sheets.read import open_workbook

ERROR_VALUES = ("#REF!", "#DIV/0!", "#NAME?", "#VALUE!", "#N/A", "#NUM!", "#NULL!", "#SPILL!", "#CALC!")
REFERENCE = re.compile(
    r"(?:(?:'([^']+)'|([A-Za-z_][\w.]*))!)?\$?([A-Z]{1,3})\$?(\d+)(?::\$?([A-Z]{1,3})\$?(\d+))?"
)
MAGIC_NUMBER = re.compile(r"(?<![\w.$:!'])(\d+\.\d+|\d{2,})(?![\w.!:(])")
NUMBER_FORMAT = re.compile(r"[0#]")


@dataclass
class Finding:
    level: str  # "error" or "hint"
    where: str
    message: str


def _column_number(letters: str) -> int:
    number = 0
    for char in letters:
        number = number * 26 + ord(char) - 64
    return number


def _references(formula: str, sheet: str, names: set[str]) -> tuple[set[tuple[str, int, int]], list[str]]:
    """Cells a formula reads (ranges up to 2000 cells are expanded), and the sheet names it mentions."""
    from openpyxl.formula import Tokenizer

    cells: set[tuple[str, int, int]] = set()
    mentioned: list[str] = []
    try:
        tokens = Tokenizer(formula).items
    except Exception:
        return cells, mentioned
    for token in tokens:
        if token.type != "OPERAND" or token.subtype != "RANGE":
            continue
        match = REFERENCE.fullmatch(token.value)
        if not match:
            continue
        target = match.group(1) or match.group(2) or sheet
        if match.group(1) or match.group(2):
            mentioned.append(target)
        column_a, row_a = _column_number(match.group(3)), int(match.group(4))
        column_b = _column_number(match.group(5)) if match.group(5) else column_a
        row_b = int(match.group(6)) if match.group(6) else row_a
        if (abs(column_b - column_a) + 1) * (abs(row_b - row_a) + 1) > 2000:
            continue
        for column in range(min(column_a, column_b), max(column_a, column_b) + 1):
            for row in range(min(row_a, row_b), max(row_a, row_b) + 1):
                cells.add((target, column, row))
    return cells, mentioned


def _cycles(graph: dict[tuple[str, int, int], set[tuple[str, int, int]]]) -> list[tuple[str, int, int]]:
    """Cells that are part of a loop of dependencies (iterative depth-first search)."""
    state: dict[tuple[str, int, int], int] = {}
    in_loop: list[tuple[str, int, int]] = []
    for start in graph:
        if state.get(start):
            continue
        stack = [(start, iter(graph.get(start, ())))]
        state[start] = 1
        path = [start]
        while stack:
            node, children = stack[-1]
            advanced = False
            for child in children:
                if child not in graph:
                    continue
                if state.get(child) == 1:
                    in_loop.extend(path[path.index(child) :])
                elif not state.get(child):
                    state[child] = 1
                    path.append(child)
                    stack.append((child, iter(graph.get(child, ()))))
                    advanced = True
                    break
            if not advanced:
                state[node] = 2
                path.pop()
                stack.pop()
    return list(dict.fromkeys(in_loop))


def check_workbook(data: bytes) -> list[Finding]:
    formulas_book = open_workbook(data)
    values_book = open_workbook(data, values=True)
    sheet_names = {s.title for s in formulas_book.worksheets}
    names = set(formulas_book.defined_names.keys())
    findings: list[Finding] = []
    graph: dict[tuple[str, int, int], set[tuple[str, int, int]]] = {}
    for sheet in formulas_book.worksheets:
        stored = values_book[sheet.title]
        for row in sheet.iter_rows():
            for cell in row:
                value: Any = cell.value
                where = f"{sheet.title}!{cell.coordinate}"
                shown = stored[cell.coordinate].value
                if isinstance(shown, str) and shown in ERROR_VALUES:
                    findings.append(Finding("error", where, f"shows {shown}"))
                if not (isinstance(value, str) and value.startswith("=")):
                    continue
                if any(e in value for e in ERROR_VALUES):
                    findings.append(Finding("error", where, f"the formula contains an error value: {value}"))
                cells, mentioned = _references(value, sheet.title, names)
                for other in mentioned:
                    if other not in sheet_names:
                        findings.append(
                            Finding("error", where, f"refers to a sheet that does not exist: '{other}'")
                        )
                graph[(sheet.title, cell.column, cell.row)] = cells
                if (
                    isinstance(shown, str)
                    and shown not in ERROR_VALUES
                    and NUMBER_FORMAT.search(cell.number_format or "")
                ):
                    findings.append(
                        Finding(
                            "error", where, f"formula gives text {shown!r} in a cell formatted as a number"
                        )
                    )
                stripped = re.sub(r'"[^"]*"', '""', value)
                stripped = re.sub(r"\$?[A-Z]{1,3}\$?\d+", "", stripped)
                if MAGIC_NUMBER.search(stripped):
                    findings.append(
                        Finding(
                            "hint",
                            where,
                            f"a number is typed inside the formula ({value[:60]}): put it in a labelled cell or a named range",
                        )
                    )
    from forge.sheets.inputs import unmarked_inputs

    loose = unmarked_inputs(formulas_book)
    if loose:
        findings.append(
            Finding(
                "hint",
                loose[0],
                f"{len(loose)} number(s) that formulas depend on are not styled as inputs ({', '.join(loose[:4])}{', ...' if len(loose) > 4 else ''}): "
                "colour them blue (the modelling convention) so a reader sees what may be changed; build_workbook does this by default",
            )
        )
    for sheet in formulas_book.worksheets:
        findings += chart_findings(sheet)
    for sheet_name, column, row in _cycles(graph):
        findings.append(
            Finding(
                "error",
                f"{sheet_name}!{_column_letters(column)}{row}",
                "circular reference: this cell depends on itself",
            )
        )
    return findings


def _points(reference: str) -> int:
    """How many cells a chart series reference such as 'Budget'!$C$2:$N$2 covers."""
    from openpyxl.utils.cell import range_boundaries

    cells = reference.rsplit("!", 1)[-1].replace("$", "")
    try:
        min_col, min_row, max_col, max_row = range_boundaries(cells)
    except ValueError:
        return 0
    return int((max_col - min_col + 1) * (max_row - min_row + 1))


def chart_findings(sheet: Any) -> list[Finding]:
    """Chart faults however the workbook was made (W6, D-532): in run doc-3 a model wrote its own openpyxl script, and its monthly balance
    chart came out as twelve one-value series, which no outline check could see."""
    findings: list[Finding] = []
    charts = list(getattr(sheet, "_charts", []))
    for number, chart in enumerate(charts, start=1):
        where = f"{sheet.title} chart {number}"
        kind = type(chart).__name__
        series = list(chart.series)
        points = [
            _points(s.val.numRef.f) if s.val is not None and s.val.numRef is not None else 0 for s in series
        ]
        if len(series) >= 3 and all(count == 1 for count in points):
            findings.append(
                Finding(
                    "error",
                    where,
                    f"{len(series)} series of one value each: the data was read along the wrong direction (a row of values is ONE series). "
                    "In build_workbook give the row as data; in openpyxl use add_data(ref, from_rows=True)",
                )
            )
        if kind not in ("PieChart", "DoughnutChart") and len(series) == 1 and chart.varyColors is not False:
            findings.append(
                Finding(
                    "hint",
                    where,
                    "one series without varyColors=False: Excel colours every point differently and lists the categories in the legend; "
                    "set chart.varyColors = False and chart.legend = None (build_workbook does both)",
                )
            )
    properties = sheet.sheet_properties.pageSetUpPr
    if charts and not (properties is not None and properties.fitToPage):
        findings.append(
            Finding(
                "hint",
                sheet.title,
                "the sheet has a chart but is not set to print one page wide, so the chart can be cut at the page edge: "
                "sheet.sheet_properties.pageSetUpPr.fitToPage = True, page_setup.fitToWidth = 1, fitToHeight = 0 (build_workbook does this)",
            )
        )
    return findings


def _column_letters(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def describe_findings(findings: list[Finding], limit: int = 40) -> str:
    errors = [f for f in findings if f.level == "error"]
    hints = [f for f in findings if f.level == "hint"]
    if not findings:
        return "No formula faults found."
    lines = [f"{len(errors)} error(s), {len(hints)} hint(s):"]
    lines += [f"  ERROR {f.where}: {f.message}" for f in errors[:limit]]
    lines += [f"  hint  {f.where}: {f.message}" for f in hints[: max(0, limit - len(errors))]]
    return "\n".join(lines)
