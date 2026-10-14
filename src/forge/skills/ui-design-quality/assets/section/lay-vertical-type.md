---
id: lay-vertical-type
type: section
title: "Composition: Vertical type sign"
summary: "An oversized vertical word like a shop sign beside a quiet text block and a drawn paper lantern; set for Japanese or East Asian type."
moods: [dramatic, night, craft]
products: [late-night food, japanese brands, bars, craft]
tags: [plain html, css, composition, layout, drawn svg art, no build step, dark]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-354, compositions for plain HTML pages)"
tested: "rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing, looked at (tests/test_compositions.py, D-354)"
files:
  - from: recipes/compositions/vertical-type.html
    to: compositions/vertical-type.html
---
A complete, working composition in plain HTML and CSS with a drawn SVG motif (so the page has imagery that belongs to it). Open the file to see it,
then lift the section and its CSS into your page: change the words to the product's real copy, redraw or replace the SVG with art that belongs to the
product, replace the `:root` block with the tokens exported from DESIGN.md (`design_md_export css-variables`) and link the fonts you fetched. Use it as the
layout of one candidate in `design_candidates`; do not use it unchanged for a product it was not made for.
