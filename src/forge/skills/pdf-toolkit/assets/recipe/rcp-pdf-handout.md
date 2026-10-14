---
id: rcp-pdf-handout
type: recipe
title: "One-page handout"
summary: "An outline for a PDF handout: a purpose paragraph, a short to-do list, a contacts table, footer with page number."
moods: [clean, plain]
products: [training, onboarding, events]
tags: [pdf, handout]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-347, scripts/dev/make_document_templates.py)"
tested: "built to PDF and rendered; header, list and table looked at (D-347)"
files:
  - from: templates/handout.json
    to: docs/handout-outline.json
---
Copy it, replace the text, then build_pdf and look at the pages with preview_file.
