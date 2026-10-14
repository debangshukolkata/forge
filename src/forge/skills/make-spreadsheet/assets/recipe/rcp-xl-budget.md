---
id: rcp-xl-budget
type: recipe
title: "Monthly budget with an assumptions sheet"
summary: "An outline for a three-month budget: an Assumptions sheet with named growth, cost growth and tax rates, formulas for revenue, costs, profit and tax, a total row and a chart."
moods: [clean, formal]
products: [finance, planning, small business]
tags: [excel, budget, formulas, named ranges]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-347, scripts/dev/make_document_templates.py)"
tested: "built into a workbook, checked with check_workbook and calculated by Excel with no error cells (D-347)"
files:
  - from: templates/budget.json
    to: docs/budget-outline.json
---
Copy it, change the labels and numbers, add months by adding rows (keep the formulas pointing at the row above), then build_workbook and check_workbook. Inputs live in Assumptions; no number is typed inside a formula.
