---
id: sec-split-band
type: section
title: Split band
summary: "A full-width band split in two halves that touch the page edges: a photograph on one side, a dark or cream panel with the words on the other."
moods: [dramatic, calm, crafted, warm]
products: [bakery, workshop, restaurant, shop, studio, brewery]
tags: [react, tailwind v4, tokens only, story, band, photography]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-435)"
preview: assets/preview/sec-split-band.jpg
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-435)"
files:
  - from: recipes/sections/SplitBand.tsx
    to: src/sections/SplitBand.tsx
---

## Split band

Component `SplitBand` in `src/sections/SplitBand.tsx`. Every prop has a default (example content): pass your own words and pictures. `tone` is dark (use once per page, for the craft or process step) or light (an invitation or a visit); `side` puts the picture left or right. Give `src` and `alt`, or pass a picture as children. It uses only the theme token classes of `index.css`
(brand-*, ink-*, btn-primary, eyebrow, font-display), so changing the tokens restyles it. Needs the `index.css` token file (asset `tpl-landing-charity`, `tpl-landing-saas` or
`tpl-landing-portfolio` ships one, or copy `recipes/index.css`).

Rules: the picture is flush to the band with no frame and shows the work or the place (hands shaping dough, the shop front); alternate `side` between two bands so the page has rhythm; keep the dark tone to one band per page; check contrast of every line on the dark panel. This serves the craft and invitation steps of a story.
