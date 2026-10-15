---
id: sec-hero-split
type: section
title: "Hero: message and visual side by side"
summary: "Eyebrow, headline, text, two actions and key facts on the left; a visual on the right (below on a phone)."
moods: [warm, friendly, editorial]
products: [charity, events, portfolio, landing]
tags: [react, tailwind v4, tokens only, hero]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-273)"
preview: assets/preview/sec-hero-split.jpg
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-273)"
files:
  - from: recipes/sections/HeroSplit.tsx
    to: src/sections/HeroSplit.tsx
  - from: recipes/sections/ArtTile.tsx
    to: src/sections/ArtTile.tsx
---

## Hero: message and visual side by side

Component `HeroSplit` in `src/sections/HeroSplit.tsx`. Every prop has a default (example content): pass your own words, numbers and links.
It uses only the theme token classes of `index.css` (brand-*, ink-*, rounded-card, shadow-soft, btn-primary, btn-secondary, card, eyebrow,
field, font-display), so changing the tokens restyles it. The file's first comment says how to use it. Needs the `index.css` token file
(asset `tpl-landing-charity`, `tpl-landing-saas` or `tpl-landing-portfolio` ships one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view, and check the page at 375 px.
