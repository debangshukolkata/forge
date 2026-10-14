---
id: rcp-xl-tracker
type: recipe
title: "Task tracker with drop-downs and colour flags"
summary: "An outline for a task list as an Excel table: status and priority drop-downs, green for Done, red for High priority, dates formatted, header frozen."
moods: [clean, practical]
products: [projects, operations, teams]
tags: [excel, tracker, validation, conditional formatting]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-347, scripts/dev/make_document_templates.py)"
tested: "built into a workbook, checked with check_workbook and calculated by Excel with no error cells (D-347)"
files:
  - from: templates/tracker.json
    to: docs/tracker-outline.json
---
Copy it, rename the columns and drop-down choices, then build_workbook. Rows beyond the sample are covered by the validation ranges (to row 200).
