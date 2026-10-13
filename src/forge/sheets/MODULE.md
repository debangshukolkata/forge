# sheets

Excel workbooks (TODO W2, D-339): an outline (`spec.py`, JSON or YAML) becomes a real .xlsx (`build.py`, openpyxl, optional extra `forge[docs]`) with real
formulas, named ranges, number and date formats, tables, conditional formatting, data validation, frozen panes, column widths and native charts.
`read.py` reads a workbook with its formulas and its last calculated values; `edit.py` changes cells, formulas, formats and sheets in an existing one;
`check.py` finds formula faults without a spreadsheet program (error values, references to sheets or names that do not exist, circular references,
formulas that return text where numbers are expected, hard-coded numbers beside formulas); `excel.py` has Excel itself recalculate the file when Excel
is installed (Windows only) so the values and errors are the real ones. The tools are in `tools/workbook.py`; the skill is `skills/make-spreadsheet/SKILL.md`.

- **Depends on:** errors, toolkit
- **Invariants:** openpyxl is imported lazily (a missing library is a clear message); an existing workbook with charts, pictures or macros is never silently stripped (openpyxl would drop them): editing it is refused unless the caller says the loss is fine; macros (.xlsm) are never run and Excel gets its paths through environment variables with macros force-disabled (D-202); a formula is never replaced by its value.
- **Tests:** test_sheets.py
- **Decisions:** docs/DECISIONS.md (D-339); clean-room rules in docs/DOCUMENTS_CLEAN_ROOM.md.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.
