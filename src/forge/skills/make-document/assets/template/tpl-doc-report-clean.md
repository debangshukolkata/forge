---
id: tpl-doc-report-clean
type: template
title: "Report: summary, results table, next steps"
summary: "A one-page business report in navy: title, summary, a key-figures table with a repeating header row, numbered next steps, header and footer with page number."
moods: [formal, clean, trustworthy]
products: [finance, management, operations]
tags: [word, report, table]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-347, scripts/dev/make_document_templates.py)"
tested: "built by the document builder, opened and printed by Word (page picture looked at), package validator clean (D-347)"
files:
  - from: templates/report-clean.docx
    to: docs/templates/report-clean.docx
---
Use it as the `template` of a document outline (`"template": "docs/templates/report-clean.docx"`): its styles, header and footer are kept and its sample text is removed. Change the header and footer text with edit_document, and the brand with a brand file.
