---
id: sec-category-tiles
type: section
title: Category tiles
summary: "Three large tiles that lead to the parts of a shop or site; the first one filled with the brand colour."
moods: [clean, confident]
products: [shop, e-commerce, navigation]
tags: [react, tailwind v4, tokens only, categories]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-385)"
preview: assets/preview/sec-category-tiles.jpg
tested: "built with Vite + Tailwind v4 with the template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px (tests/test_sections.py, D-385)"
files:
  - from: recipes/sections/CategoryTiles.tsx
    to: src/sections/CategoryTiles.tsx
---

## Category tiles

Component `CategoryTiles` in `src/sections/CategoryTiles.tsx`. Every prop has a default (example content): pass your own words, numbers and links. It uses only the theme token classes of `index.css` (brand-*, ink-*, rounded-card, shadow-soft, btn-primary, btn-secondary, card, eyebrow, font-display), so changing the tokens restyles it. The file's first comment says how to use it. Needs the `index.css` token file (any `tpl-*` template ships one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view, and check the page at 375 px.
