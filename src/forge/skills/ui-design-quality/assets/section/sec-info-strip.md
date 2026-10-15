---
id: sec-info-strip
type: section
title: Info strip
summary: "A ruled strip of practical facts (hours, address, delivery) with a label above each value between hairlines, instead of three boxes."
moods: [calm, clear, editorial]
products: [bakery, restaurant, shop, studio, clinic, venue]
tags: [react, tailwind v4, tokens only, facts, card-free]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-433)"
preview: assets/preview/sec-info-strip.jpg
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-433)"
files:
  - from: recipes/sections/InfoStrip.tsx
    to: src/sections/InfoStrip.tsx
---

## Info strip

Component `InfoStrip` in `src/sections/InfoStrip.tsx`. Every prop has a default (example content): pass your own `items` (label, value and an optional note). Two to four items; the row
stacks on a phone. It uses only the theme token classes of `index.css`, so changing the tokens restyles it. Needs the `index.css` token file (asset `tpl-landing-charity`,
`tpl-landing-saas` or `tpl-landing-portfolio` ships one, or copy `recipes/index.css`).

Rules: put it directly under the hero when the brief asks for hours, an address or how to order; facts are information, not objects, so they are not set in cards (the card-density
check and the uneven-cards check both exist because the first Fernhill Bakery build set exactly this in three boxes of different heights). Replace the example copy completely.
