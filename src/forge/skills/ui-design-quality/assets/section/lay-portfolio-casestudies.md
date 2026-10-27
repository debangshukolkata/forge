---
id: lay-portfolio-casestudies
type: section
title: "Composition: Portfolio with case studies"
summary: "A monochrome editorial portfolio: masonry grid of drawn work tiles, case-study cards with a one-line result, an about strip and a contact line."
moods: [editorial, minimal, refined]
products: [designer portfolios, photographer portfolios, studios, freelancers, agencies]
tags: [plain html, css, composition, layout, drawn svg art, no build step, light, portfolio, masonry, case studies]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (BO9, 2026-10-27)"
tested: "rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions.py, BO9)"
files:
  - from: recipes/compositions/portfolio-casestudies.html
    to: compositions/portfolio-casestudies.html
---
A complete, working composition in plain HTML and CSS with a drawn SVG motif (so the page has imagery that belongs to it). Open the file to see it,
then lift the section and its CSS into your page: change the words to the product's real copy, redraw or replace the SVG with art that belongs to the
product, replace the `:root` block with the tokens exported from DESIGN.md (`design_md_export css-variables`) and link the fonts you fetched. Use it as the
layout of one candidate in `design_candidates`; do not use it unchanged for a product it was not made for.
