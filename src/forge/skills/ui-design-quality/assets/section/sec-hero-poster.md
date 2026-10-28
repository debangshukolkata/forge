---
id: sec-hero-poster
type: section
title: Poster hero
summary: "Giant uppercase type on a solid brand-colour field, edge to edge, with a thin information bar and one button under it."
moods: [loud, bold, energetic]
products: [event, festival, launch, campaign, conference, sale]
tags: [react, tailwind v4, tokens only, hero, poster, big type]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-hero-poster.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/HeroPoster.tsx
    to: src/sections/HeroPoster.tsx
---

## Poster hero

Component `HeroPoster` in `src/sections/HeroPoster.tsx`. Every prop has a default (example content): pass your own words and links. `title` is one to three short lines; `details` fills the bar (when, where, price). White text on the brand colour: the token files keep the contrast. Choose it for events and campaigns, not for a quiet product. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
