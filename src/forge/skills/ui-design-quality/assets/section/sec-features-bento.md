---
id: sec-features-bento
type: section
title: "Features: bento grid"
summary: "Unequal tiles, each with one idea; one tall, wide and dark tile for rhythm."
moods: [modern, organised]
products: [saas, apps, overview]
tags: [react, tailwind v4, tokens only, features]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-273)"
preview: assets/preview/sec-features-bento.jpg
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-273)"
files:
  - from: recipes/sections/FeaturesBento.tsx
    to: src/sections/FeaturesBento.tsx
  - from: recipes/sections/ArtTile.tsx
    to: src/sections/ArtTile.tsx
---

## Features: bento grid

Component `FeaturesBento` in `src/sections/FeaturesBento.tsx`. Every prop has a default (example content): pass your own words, numbers and links.
It uses only the theme token classes of `index.css` (brand-*, ink-*, rounded-card, shadow-soft, btn-primary, btn-secondary, card, eyebrow,
field, font-display), so changing the tokens restyles it. The file's first comment says how to use it. Needs the `index.css` token file
(asset `tpl-landing-charity`, `tpl-landing-saas` or `tpl-landing-portfolio` ships one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view, and check the page at 375 px.
