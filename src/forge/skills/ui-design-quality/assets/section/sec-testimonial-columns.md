---
id: sec-testimonial-columns
type: section
title: Testimonial columns
summary: "Three short quotes side by side as plain text between hairlines, with the name and role under each; no boxes, no stars."
moods: [warm, human, quiet]
products: [school, clinic, service, studio, shop, nonprofit]
tags: [react, tailwind v4, tokens only, testimonial, quotes, columns, social proof]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-testimonial-columns.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/TestimonialColumns.tsx
    to: src/sections/TestimonialColumns.tsx
---

## Testimonial columns

Component `TestimonialColumns` in `src/sections/TestimonialColumns.tsx`. Every prop has a default (example content): pass your own words and links. `items` is a list of text, name and role; use real quotes with one concrete detail each. Pairs with `TestimonialFeature` (one long quote). It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
