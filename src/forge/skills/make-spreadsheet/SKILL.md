---
name: make-spreadsheet
description: Build, read, edit and check Excel workbooks (.xlsx) with real formulas, named ranges, formats, tables, validation, conditional formatting and charts. Use when the user wants a spreadsheet, a budget, a model, a tracker or a data table in Excel.
---

# Making Excel workbooks

Tools: `build_workbook` (from an outline), `read_workbook`, `edit_workbook`, `check_workbook`. Written for DebCraft from the Office Open XML
specification, the openpyxl documentation and our own tests with Excel.

## Rules that make a workbook worth opening
1. **Formulas, never pasted results.** A total is `=SUM(B2:B13)`, not 1240. If you computed a number in your head, put the inputs in cells and the
   calculation in a formula, so the user can change an input and see the answer move.
2. **Inputs in one place.** Rates, targets and dates go in a labelled `Assumptions` sheet (or a block at the top), each used through a
   named range (`names` in the outline: `TaxRate` -> `Assumptions!$B$2`). A number typed inside a formula (`=B2*1.2`) is a hidden input:
   `check_workbook` lists it as a hint.
2b. **Inputs look like inputs.** A number that a formula depends on (a rate, a target, a starting value) is styled blue, the modelling convention, so a reader
   sees at a glance what may be changed and what is calculated. `build_workbook` does it for you (`mark_inputs`, on by default, also through named ranges);
   `check_workbook` hints at any such number that is not styled that way.
3. **One header row, one record per row, one kind of value per column.** No blank rows or columns inside the data, no merged cells in the data, no
   units inside numbers ("12 kg"): put the unit in the header.
4. **Formats say what a number is.** Currency `#,##0.00`, percentages `0.0%` (store 0.2, not 20), dates `yyyy-mm-dd`, counts `#,##0`. Dates are real
   dates, not text.
5. **Make it readable:** a header row that stands out, widths that fit (`width` per column), the header row frozen (default), a total row
   (`total_row`), an Excel table (`table: true`) for data people will filter and sort.
6. **Guard the inputs:** `validations` with `choices` for category columns, `whole` or `decimal` limits for quantities. `conditional` formatting
   to flag what needs attention (`greater_than`, `less_than`, `between`, `text_contains`, `color_scale`, `data_bar`).
7. **Native charts** (`charts`: type, `data` range with its header row, `categories` range, `anchor`), titled, one message per chart.
8. **Say where facts came from:** `notes` gives cell comments ("Source: finance report, page 4").

## Outline format (JSON or YAML)
```json
{"title": "Budget",
 "sheets": [
  {"name": "Assumptions", "columns": [{"header": "Item"}, {"header": "Value", "format": "0.0%"}], "rows": [["Tax rate", 0.2]]},
  {"name": "Sales",
   "columns": [{"header": "Region", "width": 18}, {"header": "Q1", "format": "#,##0"}, {"header": "Tax", "format": "#,##0"}],
   "rows": [["North", 100, "=B2*TaxRate"], ["South", 80, "=B3*TaxRate"]],
   "total_row": {"A": "Total", "B": "SUM", "C": "SUM"},
   "validations": [{"range": "A2:A9", "choices": ["North", "South"]}],
   "conditional": [{"range": "B2:B3", "rule": "greater_than", "value": 90}],
   "charts": [{"type": "column", "title": "Sales by region", "data": "B1:B3", "categories": "A2:A3", "anchor": "F2"}]}],
 "names": {"TaxRate": "Assumptions!$B$2"}}
```
Row 1 is the header when `columns` is given; the data starts in row 2 (row 1 when there are no columns). A text value starting with `=` is a
formula; to store text that starts with `=`, begin it with an apostrophe-free space.

## Work loop
1. Write the outline file, `build_workbook`. The result already lists formula faults.
2. `check_workbook` with `recalculate: true` when Excel is installed: Excel calculates every formula, lists the cells that show `#DIV/0!`, `#REF!`,
   `#NAME?` and so on, and stores the calculated values in the file (a file made by a library has none until Excel opens it, which matters for
   viewers that do not calculate, such as previews and some phone apps). Fix every error and check again.
3. Without Excel the static check still finds missing sheets, circular references, error text in formulas and text results in number-formatted cells.
   Say in your answer that the values were not calculated by Excel.
4. Look at it: `preview_file` prints the workbook with Excel (when installed) and gives page pictures and a contact sheet; check column widths (no `####`),
   charts, header rows and page breaks. `critique_document` gives an independent review for workbooks that go to other people.
5. Changing an existing workbook: `read_workbook` first, then `edit_workbook`. Charts, pictures and macros in an existing file would be lost by
   the editing library, so the tool refuses until you have asked the user and set `allow_loss`. Renaming a sheet does not update the formulas in other
   sheets: check them.

## Do not
- Do not paste a computed value where a formula belongs; do not leave `#REF!` or `#DIV/0!` showing (wrap divisions: `=IF(B2=0,0,A2/B2)`).
- Do not enable or write macros; the result is always `.xlsx`.
- Do not claim the numbers are right because the workbook has no errors: say which source each input came from.

## Starting points and the company look
`find_asset` (type `recipe`, e.g. "budget", "task tracker") copies a tested outline to adapt. `brand` in the outline, or `brand_file` on `build_workbook`
(accent, text, body_font), colours the header rows and sets the cell font.

## Messy data in: `clean_table`
A CSV, TSV or sheet from an export is rarely ready: title lines above the header, a header over two rows, blank rows, numbers stored as text
("1,234.50", "(300)", "12%", "$1,200"), dates in mixed formats, duplicates, a total line at the bottom. `clean_table` fixes what can be fixed without
guessing and writes a clean workbook (an Excel table with a frozen header, real numbers and dates, number formats). It REPORTS every change and every doubt:
pass that report on to the user. A date column that no value settles (01/02/2026) is read day first and reported as a guess; ask the user when it matters.
Total lines are kept as data and flagged: replace them with a total row of formulas (`total_row`) in a later `build_workbook` from the saved outline
(`outline_output`). Never clean in place: the original file stays untouched.
