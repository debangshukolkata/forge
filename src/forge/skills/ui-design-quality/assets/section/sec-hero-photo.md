---
id: sec-hero-photo
type: section
title: Photography-led hero
summary: "One large photograph runs to the edge of the page and fades into the page colour where the headline sits; light display type, a button and three trust points."
moods: [warm, appetising, editorial, calm]
products: [bakery, restaurant, cafe, shop, hotel, studio, farm]
tags: [react, tailwind v4, tokens only, hero, photography, full-bleed]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-435)"
preview: assets/preview/sec-hero-photo.jpg
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-435)"
files:
  - from: recipes/sections/HeroPhoto.tsx
    to: src/sections/HeroPhoto.tsx
---

## Photography-led hero

Component `HeroPhoto` in `src/sections/HeroPhoto.tsx`. Every prop has a default (example content): pass your own words and pictures. Give `src` and `alt` for a real photograph (the picture is the protagonist); without them a drawn stand-in is shown. The headline is set `font-light` at a large size; keep it to three short lines. It uses only the theme token classes of `index.css`
(brand-*, ink-*, btn-primary, eyebrow, font-display), so changing the tokens restyles it. Needs the `index.css` token file (asset `tpl-landing-charity`, `tpl-landing-saas` or
`tpl-landing-portfolio` ships one, or copy `recipes/index.css`).

Rules: the photograph must show the product itself (the loaf, the dish, the room), landscape and large, with the subject on the right under the fade; never a stock smile. Replace the example copy completely and the stand-in before the page ships (the audit calls a few drawn shapes a placeholder). On a phone the text comes first and the photograph follows. This is the desire step of a story.
