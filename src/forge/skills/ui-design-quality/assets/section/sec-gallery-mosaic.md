---
id: sec-gallery-mosaic
type: section
title: Gallery mosaic
summary: Six captioned tiles of different sizes (one large, tall and wide ones) with drawn shapes or your photographs, instead of a grid of identical squares.
moods: [editorial, playful, crafted]
products: [studio, portfolio, restaurant, shop, event]
tags: [react, tailwind v4, tokens only, gallery, imagery]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-432)"
preview: assets/preview/sec-gallery-mosaic.jpg
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-432)"
files:
  - from: recipes/sections/GalleryMosaic.tsx
    to: src/sections/GalleryMosaic.tsx
---

## Gallery mosaic

Component `GalleryMosaic` in `src/sections/GalleryMosaic.tsx`. Every prop has a default (example content): pass your own `tiles` (caption, tone brand, ink, soft or pale,
shape arch, circle, stripes or bars, or `src` and `alt` for a real photograph that fills the tile). The drawn shapes are stand-ins: the page is better with real pictures
(`find_image`, the project's `brand-assets` folder, `generate_image`). It uses only the theme token classes of `index.css`. Needs the `index.css` token file (asset
`tpl-landing-charity`, `tpl-landing-saas` or `tpl-landing-portfolio` ships one, or copy `recipes/index.css`).

Rules: exactly six tiles (the spans repeat every six); write real captions; every photograph has alt text; check the page at 375 px, where it becomes two columns.
