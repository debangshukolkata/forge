"""Turn a messy CSV, TSV or Excel sheet into a clean table, ready for `build_workbook` (TODO W2, D-355).

Real exports have title lines above the header, a header over two rows, blank rows and columns, numbers written as text ("1,234.50", "(300)", "12%",
"$1,200", "N/A"), dates in mixed or ambiguous formats, stray spaces and non-breaking spaces, duplicate rows and a total line at the bottom. `clean_table`
fixes what can be fixed without guessing and REPORTS every change and every doubt, so nothing is altered silently:
numbers and percentages become numbers with a number format, dates become dates (day-first or month-first decided from the whole column, and said),
empty-looking cells become empty, text is trimmed, duplicates and blank lines are removed. The result is an outline for `build_workbook`."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from forge.sheets.build import load_openpyxl
from forge.sheets.spec import WorkbookError

EMPTY_WORDS = {"", "n/a", "na", "null", "none", "-", "--", "—", "#n/a", "nan", "tbd", "?"}
NUMBER = re.compile(
    r"^\(?-?[$€£₹¥]?\s?\(?-?\d{1,3}(?:[, ]\d{3})*(?:\.\d+)?\)?%?$|^\(?-?[$€£₹¥]?\s?\(?-?\d+(?:\.\d+)?\)?%?$"
)
MONTHS = {
    m: i
    for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1
    )
}
TEXT_DATE = re.compile(
    r"^(?:(\d{1,2})[ -]([A-Za-z]{3})[a-z]*[ -,]*(\d{2,4})|([A-Za-z]{3})[a-z]*[ -](\d{1,2}),?[ -](\d{2,4}))$"
)
NUMERIC_DATE = re.compile(r"^(\d{1,4})[/.\-](\d{1,2})[/.\-](\d{1,4})$")
MAX_ROWS = 200_000
CURRENCY_FORMATS = {
    "$": '"$"#,##0.00',
    "€": '"€"#,##0.00',
    "£": '"£"#,##0.00',
    "₹": '"₹"#,##0.00',
    "¥": '"¥"#,##0',
}


@dataclass
class CleanResult:
    columns: list[dict[str, Any]]
    rows: list[list[Any]]
    report: list[str] = field(default_factory=list)

    def outline(self, sheet_name: str = "Data", title: str = "") -> dict[str, Any]:
        """A workbook outline for `build_workbook`: one sheet, an Excel table, the cleaned columns and formats."""
        return {
            "title": title,
            "sheets": [
                {
                    "name": sheet_name[:31],
                    "columns": self.columns,
                    "rows": self.rows,
                    "table": bool(self.rows),
                }
            ],
        }


def _text(cell: Any) -> str:
    return re.sub(r"\s+", " ", str(cell).replace(chr(0xA0), " ")).strip() if cell is not None else ""


def read_rows(data: bytes, name: str) -> list[list[Any]]:
    lowered = name.lower()
    if lowered.endswith((".xlsx", ".xlsm")):
        from forge.ooxml.check import check_package

        openpyxl = load_openpyxl()
        check_package(data)
        try:
            book = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception as error:
            raise WorkbookError(
                f"{name} could not be read as an Excel workbook ({type(error).__name__})"
            ) from error
        return [
            list(r)
            for _, r in zip(range(MAX_ROWS), book.worksheets[0].iter_rows(values_only=True), strict=False)
        ]
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    dialect: Any
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return [r for _, r in zip(range(MAX_ROWS), csv.reader(io.StringIO(text), dialect), strict=False)]


def _filled(row: list[Any]) -> int:
    return sum(1 for c in row if _text(c).lower() not in EMPTY_WORDS)


def _header_and_body(rows: list[list[Any]], report: list[str]) -> tuple[list[str], list[list[Any]]]:
    kept = [r for r in rows if _filled(r) > 0]
    if len(kept) < len(rows):
        report.append(f"{len(rows) - len(kept)} blank row(s) were dropped")
    rows = kept
    width = max(len(r) for r in rows)
    enough = max(2, (width + 1) // 2)
    start = next((i for i, r in enumerate(rows) if _filled(r) >= enough), 0)
    if start:
        report.append(
            f"{start} title line(s) above the table were dropped: "
            + " / ".join(_text(c) for r in rows[:start] for c in r if _text(c))[:140]
        )
    header_rows = [rows[start]]
    follower = start + 1
    while follower < len(rows) and len(header_rows) < 3:
        cells = [_text(c) for c in rows[follower] if _text(c)]
        if cells and all(re.fullmatch(r"(19|20)\d{2}", c) for c in cells) and len(cells) < width:
            header_rows.append(rows[follower])
            follower += 1
        else:
            break
    names: list[str] = []
    carried = ""
    for index in range(width):
        parts = []
        for level, row in enumerate(header_rows):
            cell = _text(row[index]) if index < len(row) else ""
            if cell:
                if level == 0:
                    carried = cell
                parts.append(cell)
            elif level == 0 and len(header_rows) > 1:
                parts.append(carried)
        names.append(" ".join(dict.fromkeys(p for p in parts if p)) or f"Column {index + 1}")
    if len(header_rows) > 1:
        report.append(f"a header spread over {len(header_rows)} rows was joined into one")
    seen: dict[str, int] = {}
    for position, name in enumerate(names):
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            names[position] = f"{name} ({seen[name]})"
            report.append(
                f"the column name {name!r} was used twice: the second one is called {names[position]!r}"
            )
    return names, rows[follower:]


def _number(text: str) -> tuple[float, str] | None:
    """(value, kind) for text that is a number ('number', 'percent' or a currency symbol), else None."""
    raw = text.strip()
    if not NUMBER.match(raw):
        return None
    negative = raw.startswith("(") or "-" in raw
    kind = "number"
    if raw.endswith("%"):
        kind = "percent"
    symbol = next((s for s in CURRENCY_FORMATS if s in raw), "")
    digits = re.sub(r"[^\d.]", "", raw.replace(",", ""))
    if not digits or digits.count(".") > 1:
        return None
    value = float(digits)
    if negative:
        value = -value
    if kind == "percent":
        value /= 100
    return value, (symbol or kind)


def _parse_date(text: str, day_first: bool) -> date | None:
    raw = text.strip()
    match = NUMERIC_DATE.match(raw)
    try:
        if match:
            a, b, c = (int(x) for x in match.groups())
            if match.group(1).__len__() == 4:
                return date(a, b, c)
            year = c + 2000 if c < 100 else c
            return date(year, b, a) if day_first else date(year, a, b)
        match = TEXT_DATE.match(raw)
        if match:
            if match.group(1):
                day, month, year = (
                    int(match.group(1)),
                    MONTHS.get(match.group(2).lower()),
                    int(match.group(3)),
                )
            else:
                month, day, year = (
                    MONTHS.get(match.group(4).lower()),
                    int(match.group(5)),
                    int(match.group(6)),
                )
            if month:
                return date(year + 2000 if year < 100 else year, month, day)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}[T ].*", raw):
            return datetime.fromisoformat(raw[:19]).date()
    except ValueError:
        return None
    return None


def _day_first(values: list[str]) -> tuple[bool, bool]:
    """(day first?, was it ambiguous): decided by the whole column: a first part over 12 means day first, a second part over 12 means month first."""
    first_big = second_big = False
    for value in values:
        match = NUMERIC_DATE.match(value.strip())
        if match and len(match.group(1)) <= 2:
            first_big |= int(match.group(1)) > 12
            second_big |= int(match.group(2)) > 12
    if first_big and not second_big:
        return True, False
    if second_big and not first_big:
        return False, False
    return True, not (first_big or second_big)  # nothing decides it: day first, and the doubt is reported


def clean_table(rows: list[list[Any]]) -> CleanResult:
    if not rows or not any(_filled(r) for r in rows):
        raise WorkbookError("The sheet has no data")
    report: list[str] = []
    names, body = _header_and_body(rows, report)
    width = len(names)
    grid = [[(r[i] if i < len(r) else None) for i in range(width)] for r in body]
    keep = [i for i in range(width) if any(_text(r[i]).lower() not in EMPTY_WORDS for r in grid)]
    if len(keep) < width:
        report.append(f"{width - len(keep)} empty column(s) were dropped")
    names, grid = [names[i] for i in keep], [[r[i] for i in keep] for r in grid]
    before = len(grid)
    grid = [r for r in grid if any(_text(c).lower() not in EMPTY_WORDS for c in r)]
    if len(grid) < before:
        report.append(f"{before - len(grid)} blank row(s) were dropped")
    columns: list[dict[str, Any]] = []
    for index, name in enumerate(names):
        cells = [grid[r][index] for r in range(len(grid))]
        texts = [_text(c) for c in cells]
        present = [t for t in texts if t.lower() not in EMPTY_WORDS]
        converted: list[Any] = list(cells)
        number_format: str | None = None
        native_dates = [c for c in cells if isinstance(c, (date, datetime))]
        native_numbers = [c for c in cells if isinstance(c, (int, float)) and not isinstance(c, bool)]
        if present and len(native_dates) >= 0.8 * len(present):
            converted = [c.date() if isinstance(c, datetime) else c for c in cells]
            number_format = "yyyy-mm-dd"
        elif present and len(native_numbers) >= 0.8 * len(present):
            pass
        elif (
            present
            and (parsed := [_number(t) for t in present])
            and sum(p is not None for p in parsed) >= 0.8 * len(present)
        ):
            kinds = {p[1] for p in parsed if p}
            for position, text in enumerate(texts):
                if text.lower() in EMPTY_WORDS:
                    converted[position] = None
                else:
                    got = _number(text)
                    converted[position] = got[0] if got else text
            special = kinds - {
                "number"
            }  # one currency symbol or a percent among plain numbers sets the format of the column
            kind = next(iter(special)) if len(special) == 1 else "number"
            number_format = "0.0%" if kind == "percent" else CURRENCY_FORMATS.get(kind, "#,##0.##")
            bad = [t for t in present if _number(t) is None]
            report.append(
                f"column {name!r}: text turned into numbers ({kind})"
                + (
                    f"; {len(bad)} value(s) such as {bad[0]!r} are not numbers and stay as text"
                    if bad
                    else ""
                )
            )
        elif present:
            day_first, doubtful = _day_first(present)
            dates = [_parse_date(t, day_first) for t in present]
            if sum(d is not None for d in dates) >= 0.8 * len(present):
                for position, text in enumerate(texts):
                    converted[position] = (
                        None if text.lower() in EMPTY_WORDS else (_parse_date(text, day_first) or text)
                    )
                number_format = "yyyy-mm-dd"
                report.append(
                    f"column {name!r}: text turned into dates, read {'day first' if day_first else 'month first'}"
                    + (
                        "; this is a GUESS because no date in the column settles it: check it"
                        if doubtful and any(NUMERIC_DATE.match(t) for t in present)
                        else ""
                    )
                )
            else:
                converted = [None if t.lower() in EMPTY_WORDS else t for t in texts]
        else:
            converted = [None] * len(cells)
        for position in range(len(grid)):
            grid[position][index] = converted[position]
        columns.append(
            {
                "header": name,
                **({"format": number_format} if number_format else {}),
                "width": min(
                    48, max(10, len(name) + 4, *(len(_text(v)) + 2 for v in converted[:200] if v is not None))
                )
                if converted
                else 12,
            }
        )
    seen: set[tuple[Any, ...]] = set()
    unique = []
    for row in grid:
        key = tuple(row)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    if len(unique) < len(grid):
        report.append(f"{len(grid) - len(unique)} duplicate row(s) were removed")
    totals = [r for r in unique if isinstance(r[0], str) and re.match(r"^(grand )?total", r[0].strip(), re.I)]
    if totals:
        report.append(
            f"{len(totals)} row(s) look like totals ({totals[0][0]!r}): they were kept as data; replace them with a total row of formulas"
        )
    if not report:
        report.append("the table was already clean")
    return CleanResult(
        columns,
        [
            [v.isoformat() if isinstance(v, date) and not isinstance(v, datetime) else v for v in r]
            for r in unique
        ],
        report,
    )
