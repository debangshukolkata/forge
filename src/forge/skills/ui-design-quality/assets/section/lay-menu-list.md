---
id: lay-menu-list
type: section
title: "Composition: Menu with leaders"
summary: "A printed-menu layout: numbered dishes, dotted leaders to the price, two columns, a ruled heading and a drawn bowl."
moods: [warm, refined, dark]
products: [restaurants, cafes, bars, price lists]
tags: [plain html, css, composition, layout, drawn svg art, no build step, dark]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-354, compositions for plain HTML pages)"
tested: "rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing, looked at (tests/test_compositions.py, D-354)"
files:
  - from: recipes/compositions/menu-list.html
    to: compositions/menu-list.html
preview: assets/preview/lay-menu-list-desktop.jpg
---
A complete, working composition in plain HTML and CSS with a drawn SVG motif (so the page has imagery that belongs to it). Open the file to see it,
then lift the section and its CSS into your page: change the words to the product's real copy, redraw or replace the SVG with art that belongs to the
product, replace the `:root` block with the tokens exported from DESIGN.md (`design_md_export css-variables`) and link the fonts you fetched. Use it as the
layout of one candidate in `design_candidates`; do not use it unchanged for a product it was not made for.
