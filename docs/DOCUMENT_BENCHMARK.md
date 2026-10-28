# Document benchmark (TODO W5, D-357)

`scripts/benchmark/run_document_benchmark.py <run-name>` runs three fixed tasks on the real model (`tests/benchmarks/documents`) and scores them with
deterministic checks and a blind vision judgement of the printed pages (strict anchored scale: 5 professional, 3 plain, 2 machine-made). The checks are proven by
`tests/test_document_benchmark_checks.py` on outputs made by DebCraft's own tools, so a failed check means the model's work.

| Run | What changed | Task | Checks | Wall | Cost | Judge (structure/readability/tables/polish) |
|---|---|---|---|---|---|---|
| doc-1 (2026-10-15) | first run, W0-W4 tools and skills | Word sales summary | 8/8 | 299 s | $0.37 | 4/4/4/3 |
| doc-1 | same | messy export to workbook | 8/8 | 170 s | $0.17 | 3/4/3/2 |
| doc-1 | same | PDF handout | 7/7 | 186 s | $0.22 | 4/4/5/4 |

## What the first run showed
- All 23 checks pass: the model uses the tools (build, clean, check, preview) correctly and the files are valid. Total $0.76 for three tasks, about 11 minutes.
- The judge finds craft problems the checks cannot: (1) the workbook had **two charts, one showing only one product**, instead of one coherent chart of amount by
  product; (2) the PDF handout showed its **title twice** (the builder prints the title and the model also wrote it as a heading); (3) the Word summary scored 3 on polish.
- Actions taken: the skills now say that the title is printed for you, that a chart is one per question and excludes the total row, and that every chart is
  looked at in a preview. A rerun after these notes is the next measurement.

## Limits
One run per task, a vision judge of the same model family, three tasks. Read the facts (which checks failed, what the judge names) rather than small score differences.

## The fourteen tasks (2026-10-28, D-519 and D-520; w04 to w14 written and proven offline, not yet run on the model)
`tests/benchmarks/documents/<id>/` holds `task.md` (what DebCraft is asked), `task.json` and `seed/` (the files it starts from, built by `scripts/dev/make_document_seeds.py`).
Each task has its own checks in `scripts/benchmark/run_document_benchmark.py`, and `tests/test_document_benchmark_checks.py` proves every check on files built without a model
(an empty workspace is "not delivered", a good file passes), so a failed check on a real run means the model's work.

| Id | Asked | Output | Main checks |
|---|---|---|---|
| w01_sales_report | one-page Word summary of a CSV | sales-summary.docx | total and best region stated, table, bullets, no invented figure |
| w02_clean_and_chart | messy export to a clean workbook | orders.xlsx | real numbers, total by formula, one chart, duplicate and title lines gone |
| w03_handout | PDF handout | handout.pdf | place, date, schedule rows, contact line |
| w04_proposal | two-page Word proposal from a brief | proposal.docx | every phase price and the total, the three dates, bullets, no invented price |
| w05_letter | formal one-page letter | letter.docx | date, both address blocks, subject and body naming the child, trial dates, contact details, closing |
| w06_budget | household budget workbook | budget.xlsx | twelve month columns, totals and "left" by formula, a chart, numbers not text |
| w07_tracker | task tracker workbook | tracker.xlsx | status drop-down, real dates, frozen header, a summary sheet that counts by formula |
| w08_pdf_extract | table from a PDF into Excel | figures.xlsx | the four quarters and orders as numbers, a total formula, the yearly total in words |
| w09_pdf_merge | merge three PDFs in a given order | pack.pdf | four pages, the order, the title set, text kept as text |
| w10_pdf_form | fill a fillable PDF form | form-filled.pdf | the four fields still there and filled with the right values, form text kept |
| w11_pdf_ocr | type out a scanned page | delivery-note.docx | note number, customer, date, items, signer in a table |
| w12_word_edit | three exact edits in a Word file | minutes-updated.docx | the right date changed, the other one left alone, the new row, the old row and headings untouched |
| w13_excel_edit | extend a workbook and keep what was there | sales-margin.xlsx | margin formulas, the chart, the number format and the bold header kept |
| w14_excel_dashboard | KPI sheet, two charts, a conditional format | dashboard.xlsx | KPI formulas, a refund rate as a division, two charts, a conditional format |

What the first three runs showed (above) is still the only measured data; the other eleven have not been run. The next step is one run of all fourteen on the real model, read
for what the checks and the judge name, not for small score differences. Not covered yet: a Word letter or report made from a template the user supplies, and anything that needs
the user's own sample documents (the TODO asks for three to five).
