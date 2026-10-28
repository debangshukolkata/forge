---
id: sec-footer-centered
type: section
title: Centred footer
summary: "A large brand name, one sentence, a single row of links and the legal line, all centred."
moods: [calm, confident, editorial]
products: [studio, shop, event, restaurant, boutique]
tags: [react, tailwind v4, tokens only, footer, centred, brand]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-footer-centered.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/FooterCentered.tsx
    to: src/sections/FooterCentered.tsx
---

## Centred footer

Component `FooterCentered` in `src/sections/FooterCentered.tsx`. Every prop has a default (example content): pass your own words and links. Keep the links to five or fewer. The footer is the last, quiet word of the page. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
