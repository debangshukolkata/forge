---
id: lay-nonprofit-appeal
type: section
title: "Composition: Non-profit appeal"
summary: "A charity page: full-bleed drawn hero with a donate amount selector, impact numbers, story with pull quote, three programme cards and a newsletter footer."
moods: [warm, earthy, human, hopeful]
products: [charities, non-profits, community groups, foundations, fundraisers]
tags: [plain html, css, composition, layout, drawn svg art, no build step, light, donate, footer]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (BO9, 2026-10-27)"
tested: "rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions.py, BO9)"
files:
  - from: recipes/compositions/nonprofit-appeal.html
    to: compositions/nonprofit-appeal.html
preview: assets/preview/lay-nonprofit-appeal-desktop.jpg
---
A complete, working composition in plain HTML and CSS with a drawn SVG motif (so the page has imagery that belongs to it). Open the file to see it,
then lift the section and its CSS into your page: change the words to the product's real copy, redraw or replace the SVG with art that belongs to the
product, replace the `:root` block with the tokens exported from DESIGN.md (`design_md_export css-variables`) and link the fonts you fetched. Use it as the
layout of one candidate in `design_candidates`; do not use it unchanged for a product it was not made for.
