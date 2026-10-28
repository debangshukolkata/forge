---
id: lay-ticket-stub
type: section
title: "Composition: Ticket stubs"
summary: "Prices or plans as paper tickets with a perforated tear line and notched edges, slightly rotated."
moods: [playful, warm, friendly]
products: [museums, events, cinemas, entry prices]
tags: [plain html, css, composition, layout, drawn svg art, no build step, light]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-354, compositions for plain HTML pages)"
tested: "rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing, looked at (tests/test_compositions.py, D-354)"
files:
  - from: recipes/compositions/ticket-stub.html
    to: compositions/ticket-stub.html
preview: assets/preview/lay-ticket-stub-desktop.jpg
---
A complete, working composition in plain HTML and CSS with a drawn SVG motif (so the page has imagery that belongs to it). Open the file to see it,
then lift the section and its CSS into your page: change the words to the product's real copy, redraw or replace the SVG with art that belongs to the
product, replace the `:root` block with the tokens exported from DESIGN.md (`design_md_export css-variables`) and link the fonts you fetched. Use it as the
layout of one candidate in `design_candidates`; do not use it unchanged for a product it was not made for.
