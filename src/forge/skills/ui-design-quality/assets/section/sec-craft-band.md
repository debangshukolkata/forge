---
id: sec-craft-band
type: section
title: Craft band
summary: "A dark full-width band that turns from what is sold to how it is made: the maker's picture on one side, the story and three short steps on the other."
moods: [dramatic, crafted, warm]
products: [bakery, workshop, studio, restaurant, brewery]
tags: [react, tailwind v4, tokens only, story, process, dark band]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-434)"
preview: assets/preview/sec-craft-band.jpg
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-434)"
files:
  - from: recipes/sections/CraftBand.tsx
    to: src/sections/CraftBand.tsx
---

## Craft band

Component `CraftBand` in `src/sections/CraftBand.tsx`. Every prop has a default (example content): pass your own words and pictures. Pass your own picture as children (a photograph of hands or the process works best); the drawn stand-in is only a placeholder. It uses only the theme token classes of `index.css`
(brand-*, ink-*, rounded-card, eyebrow, font-display), so changing the tokens restyles it. Needs the `index.css` token file (asset `tpl-landing-charity`, `tpl-landing-saas` or
`tpl-landing-portfolio` ships one, or copy `recipes/index.css`).

Rules: use it once per page: the colour shift is the punctuation of the story, so it is the craft or process step, never the first or the last section. Replace the example copy completely, give the picture alt text, and check the contrast of every line on the dark surface.
