---
id: lay-event-lineup
type: section
title: "Composition: Event lineup"
summary: "A one-day festival page: poster hero with a drawn stage and crowd, time-column schedule with tracks, artist cards, three ticket tiers and a venue card."
moods: [bold, dark, energetic]
products: [festivals, conferences, concerts, club nights, meetups]
tags: [plain html, css, composition, layout, drawn svg art, no build step, dark, events, schedule, pricing]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (BO9, 2026-10-27)"
tested: "rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions.py, BO9)"
files:
  - from: recipes/compositions/event-lineup.html
    to: compositions/event-lineup.html
---
A complete, working composition in plain HTML and CSS with a drawn SVG motif (so the page has imagery that belongs to it). Open the file to see it,
then lift the section and its CSS into your page: change the words to the product's real copy, redraw or replace the SVG with art that belongs to the
product, replace the `:root` block with the tokens exported from DESIGN.md (`design_md_export css-variables`) and link the fonts you fetched. Use it as the
layout of one candidate in `design_candidates`; do not use it unchanged for a product it was not made for.
