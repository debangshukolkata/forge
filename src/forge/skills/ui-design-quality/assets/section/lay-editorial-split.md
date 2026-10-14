---
id: lay-editorial-split
type: section
title: "Composition: Editorial split"
summary: "A large serif headline with a small-caps dateline, thin rules and a tall arch of drawn landscape art."
moods: [warm, calm, editorial]
products: [care, culture, education, boutique, libraries]
tags: [plain html, css, composition, layout, drawn svg art, no build step, light]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-354, compositions for plain HTML pages)"
tested: "rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing, looked at (tests/test_compositions.py, D-354)"
files:
  - from: recipes/compositions/editorial-split.html
    to: compositions/editorial-split.html
---
A complete, working composition in plain HTML and CSS with a drawn SVG motif (so the page has imagery that belongs to it). Open the file to see it,
then lift the section and its CSS into your page: change the words to the product's real copy, redraw or replace the SVG with art that belongs to the
product, replace the `:root` block with the tokens exported from DESIGN.md (`design_md_export css-variables`) and link the fonts you fetched. Use it as the
layout of one candidate in `design_candidates`; do not use it unchanged for a product it was not made for.
