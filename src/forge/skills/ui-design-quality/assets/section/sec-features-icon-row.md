---
id: sec-features-icon-row
type: section
title: Icon row
summary: "Three or four features side by side, each with a small line icon, a title and two sentences, divided by hairlines and not boxed."
moods: [friendly, clear, light]
products: [service, trades, saas, clinic, shop, local business]
tags: [react, tailwind v4, tokens only, features, icons, row, inline svg]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-features-icon-row.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/FeaturesIconRow.tsx
    to: src/sections/FeaturesIconRow.tsx
---

## Icon row

Component `FeaturesIconRow` in `src/sections/FeaturesIconRow.tsx`. Every prop has a default (example content): pass your own words and links. The four line icons are drawn inline (nothing to install); pass your own `icon` node per item to change one. Choose it for short, parallel reasons to choose you. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
