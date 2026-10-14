---
id: tpl-doc-proposal
type: template
title: "Proposal with contents list, approach, timeline and price"
summary: "A customer proposal in teal: contents list, the problem, the approach, a phase and price table, one clear next step."
moods: [warm, persuasive, professional]
products: [sales, consulting, agency]
tags: [word, proposal, toc]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-347, scripts/dev/make_document_templates.py)"
tested: "built by the document builder, opened and printed by Word (page picture looked at), package validator clean (D-347)"
files:
  - from: templates/proposal.docx
    to: docs/templates/proposal.docx
---
Use it as the `template` of a document outline. The contents list fills when the file is opened in Word.
