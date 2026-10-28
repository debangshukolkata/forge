---
id: sec-nav-centered
type: section
title: Centred navigation
summary: "The brand in the middle of the bar, links split to its left and right, one call to action at the far right; a native menu on a phone."
moods: [calm, symmetrical, refined]
products: [restaurant, studio, shop, boutique, hotel, salon]
tags: [react, tailwind v4, tokens only, navigation, header, centred, sticky]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-nav-centered.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/NavCentered.tsx
    to: src/sections/NavCentered.tsx
---

## Centred navigation

Component `NavCentered` in `src/sections/NavCentered.tsx`. Every prop has a default (example content): pass your own words and links. `links` is split in half around the brand (keep an even number, two to six). Needs the btn-primary utility. Choose it for a calm, symmetrical top; `NavBar` is the plainer default. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
