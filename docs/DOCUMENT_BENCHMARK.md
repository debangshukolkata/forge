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

## Run doc-2 (2026-10-28): all fourteen tasks on the real model, one run each
Checks: 13 of 14 tasks passed every check (105 of 106 checks); the one miss was my check, not the model (w08 wrote the yearly-total sentence as a formula, `="Total sales for the year were " & B6`,
which is better than typed text; the check now accepts it). Cost about $1.77 for all fourteen, 47 s to 179 s each. The judge (blind, strict scale 1 to 5) gave 2 to 5; read the named problems, not the small differences.

| Task | Checks | Judge s/r/t/p | The judge's worst problem |
|---|---|---|---|
| w01 sales report | 8/8 | 4/4/4/4 | a heading repeated above the table |
| w02 clean and chart | 8/8 | 2/3/4/2 | two inconsistent charts instead of one amount-by-product chart (the same problem as doc-1) |
| w03 handout | 7/7 | 4/4/5/3 | contact section awkwardly phrased |
| w04 proposal | 9/9 | 4/5/4/4 | plain; the total price is not emphasised |
| w05 letter | 9/9 | 4/4/5/4 | large title, plain styling for a formal letter |
| w06 budget | 7/7 | 3/3/4/2 | charts misconfigured, the monthly balance is not clear |
| w07 tracker | 7/7 | 3/4/2/3 | the table is split across two printed pages, columns separated |
| w08 pdf extract | 5/6 (check fixed) | 2/3/3/2 | the total shown with odd digit grouping |
| w09 pdf merge | 6/6 | 3/3/5/2 | pages bare (the inputs were bare) |
| w10 pdf form | 6/6 | 4/4/3/3 | much empty space on the page |
| w11 pdf ocr | 7/7 | 4/4/5/4 | very plain |
| w12 word edit | 7/7 | 4/4/5/4 | plain, no advanced formatting |
| w13 excel edit | 8/8 | 2/3/4/1 | the chart on the second page is clipped by the page margins |
| w14 excel dashboard | 7/7 | 3/3/3/2 | months drawn as separate series, only part of the range shown |

**What it shows.** The model uses the tools correctly and the files are valid and do what was asked (the checks). The craft problems repeat in three places and are fixable: (1) **charts**:
w02, w06 and w14 each got a chart with the wrong series (months as separate series, or two charts where one was asked); (2) **printing**: w07's table splits across pages and w13's chart is cut by the margin,
so a workbook needs a print setup (fit to one page wide, the chart inside the print area); (3) **plain Word and PDF output** (w04, w05, w11, w12) is correct but looks like a template.
Limits: one run per task, a judge from the same model family, tasks written the day before. The three fixes are open as TODO W6 to W8.

## Run doc-3 (2026-10-29): the nine tasks behind W6 to W8, after D-525 and D-526
| Task | Checks | Judge s/r/t/p (doc-2 -> doc-3) | Worst problem now |
|---|---|---|---|
| w02 clean and chart | 8/8 | 2/3/4/2 -> 2/3/2/2 | the table: no title, a missing margin value (the chart complaint is gone) |
| w04 proposal | 8/9 | 4/5/4/4 -> 4/4/4/3 | empty space on page 2; the failed check was the checker's own fault (D-532) |
| w05 letter | 8/9 | 4/4/5/4 -> 4/4/5/4 | still plain; the failed check was the checker's own fault (D-532) |
| w06 budget | 7/7 | 3/3/4/2 -> 2/3/2/2 | twelve one-value series: the model wrote its own openpyxl script after failing to write the long JSON outline, so the builder fix never ran |
| w07 tracker | 7/7 | 3/4/2/3 -> 3/3/4/3 | no sheet title (the page split is gone) |
| w11 pdf ocr | 7/7 | 4/4/5/4 -> 5/5/5/5 | white space |
| w12 word edit | 7/7 | 4/4/5/4 -> 4/4/4/3 | plain (an edit of the user's document, so the builder does not apply) |
| w13 excel edit | 8/8 | 2/3/4/1 -> 2/3/4/2 | the seed's own chart cropped (an edit keeps the user's page setup) |
| w14 excel dashboard | 7/7 | 3/3/3/2 -> 3/3/4/2 | KPI values without percent or thousands formats (the chart complaint is gone) |

**Reading:** where the model used the builders, the named problems moved on: the chart complaints of w02 and w14 and the page split of w07 are gone and w11 scored 5 on all four. Where it bypassed them (w06's own script) or edited a user's file (w12, w13), nothing changed, so `check_workbook` now reports chart faults whatever made the file (D-532). One run each and a judge that varies by a point between runs: read the named problems, not the small score moves.

## Run doc-4 (2026-10-29): all fourteen tasks after the W6 to W8 builders and the D-532 checks
| Task | Checks | Judge s/r/t/p (doc-2 -> doc-4) | Worst problem now |
|---|---|---|---|
| w01 sales report | 8/8 | -> 5/5/5/4 | a repeated heading |
| w02 clean and chart | 8/8 | -> 2/3/4/3 | no title above the table and chart |
| w03 handout | 7/7 | -> 4/4/4/4 | plain |
| w04 proposal | 9/9 | 4/5/4/4 -> 5/5/5/4 | a heading separated from its list by a page break |
| w05 letter | 8/9, 9/9 after D-541 | 4/4/5/4 -> 4/5/5/4 | plain; the failed check was the checker's (a bold subject line without "Re:") |
| w06 budget | 7/7 | 3/3/4/2 -> 3/4/4/3 | no sheet title; the builder was used this time (doc-3: the model's own script) |
| w07 tracker | 7/7, 7/7 after D-541 | 3/4/2/3 -> 3/4/5/4 | a task cut off by a narrow column (fixed: long text wraps); no sheet title |
| w08 pdf extract | 6/6 | -> 3/4/4/3 | no title above the table |
| w09 pdf merge | 6/6 | -> 3/4/5/3 | sparse |
| w10 pdf form | 6/6 | -> 4/4/4/4 | white space |
| w11 pdf ocr | 7/7 | 4/4/5/4 -> 4/4/5/4 | white space |
| w12 word edit | 7/7 | 4/4/5/4 -> 3/3/3/3 | plain (an edit of the user's document) |
| w13 excel edit | 8/8 | 2/3/4/1 -> 3/4/4/2 | the seed's own chart split across pages (an edit keeps the user's page setup) |
| w14 excel dashboard | 7/7 | 3/3/3/2 -> 3/3/3/3 after D-541 | a KPI label cut off (fixed: long text wraps); no titles, empty space |

Cost $1.79 for the fourteen, 21 minutes. **Reading:** the model used `build_workbook` and `build_document` in every task that builds a file, w06 included; the chart and page-split complaints did not come back. Three faults found and fixed (D-541) and re-checked live on w05, w07, w14: a checker false positive on letters, text cut off by the model's own column widths, and dates written as `=DATE()` formulas. The judge's commonest complaint is now a missing title above a sheet's table (w02, w06, w07, w08, w14): next lever, not changed tonight (a title row moves the header off row 1, which the table, the freeze and the print titles rely on). One run each.

## Runs doc-5, doc-5b, doc-5c (2026-10-29): sheet titles (D-543), the four workbook tasks
| Task | doc-4 | doc-5 (titles) | after the fixes (doc-5c) | Worst problem now |
|---|---|---|---|---|
| w02 clean and chart | 8/8, 2/3/4/3 | 8/8, 3/4/4/4 (no title: the clean_table outline had none) | 8/8, 4/4/4/3 | default Excel look, total row formatting |
| w06 budget | 7/7, 3/4/4/3 | 7/7, 4/3/4/4 | - | small print |
| w07 tracker | 7/7, 3/4/5/4 | 7/7, 4/5/5/5 | - | white space |
| w14 excel dashboard | 7/7, 3/3/3/3 | 7/7, 2/3/2/2 (a chart cut by the page break; charts drew the wrong sheet) | 7/7, 4/4/4/3 | refund rate without a percent format |

**Reading:** with titles the judge stopped naming a missing title; the two faults the titles exposed (a chart across a page break, charts reading the wrong sheet) are fixed. Next lever: number formats on summary values (w14) and the total row's look (w02). One run each.

