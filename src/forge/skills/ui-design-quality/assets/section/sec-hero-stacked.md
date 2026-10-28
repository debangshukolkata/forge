---
id: sec-hero-stacked
type: section
title: Stacked hero
summary: "A left-aligned headline and one line of text, then a full-width picture band that breaks out of the text column."
moods: [calm, warm, confident]
products: [bakery, venue, restaurant, product, travel, studio]
tags: [react, tailwind v4, tokens only, hero, picture-led, full bleed]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-hero-stacked.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/HeroStacked.tsx
    to: src/sections/HeroStacked.tsx
---

## Stacked hero

Component `HeroStacked` in `src/sections/HeroStacked.tsx`. Every prop has a default (example content): pass your own words and links. Pass your own picture as children (a wide crop, about 3:1 on desktop); the drawn band is a stand-in. Choose it when the picture carries the page. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
