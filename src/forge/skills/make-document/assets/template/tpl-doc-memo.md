---
id: tpl-doc-memo
type: template
title: "Memo: To, From, Date, Subject"
summary: "A plain internal memo: a To/From/Date/Subject block, a decision-needed paragraph first, background after."
moods: [plain, direct]
products: [internal, management, hr]
tags: [word, memo]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-347, scripts/dev/make_document_templates.py)"
tested: "built by the document builder, opened and printed by Word (page picture looked at), package validator clean (D-347)"
files:
  - from: templates/memo.docx
    to: docs/templates/memo.docx
---
Use it as the `template` of a document outline. Say what you need from the reader in the first paragraph.
