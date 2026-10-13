---
id: sec-stats-row
type: section
title: Stats row
summary: Four big numbers with labels and dividers.
moods: [bold, trustworthy]
products: [charity, saas, reports]
tags: [react, tailwind v4, tokens only, numbers]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-273)"
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-273)"
files:
  - from: recipes/sections/StatsRow.tsx
    to: src/sections/StatsRow.tsx
---

## Stats row

Component `StatsRow` in `src/sections/StatsRow.tsx`. Every prop has a default (example content): pass your own words, numbers and links.
It uses only the theme token classes of `index.css` (brand-*, ink-*, rounded-card, shadow-soft, btn-primary, btn-secondary, card, eyebrow,
field, font-display), so changing the tokens restyles it. The file's first comment says how to use it. Needs the `index.css` token file
(asset `tpl-landing-charity`, `tpl-landing-saas` or `tpl-landing-portfolio` ships one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view, and check the page at 375 px.
