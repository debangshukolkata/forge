---
id: sec-product-trio
type: section
title: Product trio
summary: "A text block beside three tall product pictures with a name and a line beneath, the middle one set lower; no card frames."
moods: [warm, crafted, editorial]
products: [bakery, shop, restaurant, studio, florist]
tags: [react, tailwind v4, tokens only, products, imagery, card-free]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-434)"
preview: assets/preview/sec-product-trio.jpg
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-434)"
files:
  - from: recipes/sections/ProductTrio.tsx
    to: src/sections/ProductTrio.tsx
---

## Product trio

Component `ProductTrio` in `src/sections/ProductTrio.tsx`. Every prop has a default (example content): pass your own words and pictures. Each product takes `src` and `alt` for a real photograph; without them a drawn stand-in in the theme colours is shown. It uses only the theme token classes of `index.css`
(brand-*, ink-*, rounded-card, eyebrow, font-display), so changing the tokens restyles it. Needs the `index.css` token file (asset `tpl-landing-charity`, `tpl-landing-saas` or
`tpl-landing-portfolio` ships one, or copy `recipes/index.css`).

Rules: exactly three products; replace the example copy and the stand-ins before the page ships (the audit calls a few drawn shapes a placeholder); every photograph has alt text; check the page at 375 px, where it stacks with the text first. This is the exploration step of a story: use it after the trust strip.
