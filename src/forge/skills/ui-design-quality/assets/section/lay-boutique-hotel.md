---
id: lay-boutique-hotel
type: section
title: "Composition: Boutique hotel"
summary: "A hospitality page: full-bleed dusk hero with a drawn building and sea, a booking bar, alternating room rows, text amenities, one large guest quote and address cards."
moods: [refined, calm, elegant]
products: [hotels, guesthouses, resorts, retreats, hospitality]
tags: [plain html, css, composition, layout, drawn svg art, no build step, serif, full-bleed]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (BO9, 2026-10-27)"
tested: "rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions.py, BO9)"
files:
  - from: recipes/compositions/boutique-hotel.html
    to: compositions/boutique-hotel.html
---
A complete, working composition in plain HTML and CSS with a drawn SVG motif (so the page has imagery that belongs to it). Open the file to see it,
then lift the section and its CSS into your page: change the words to the product's real copy, redraw or replace the SVG with art that belongs to the
product, replace the `:root` block with the tokens exported from DESIGN.md (`design_md_export css-variables`) and link the fonts you fetched. Use it as the
layout of one candidate in `design_candidates`; do not use it unchanged for a product it was not made for.
