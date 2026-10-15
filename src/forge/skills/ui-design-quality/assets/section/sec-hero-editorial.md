---
id: sec-hero-editorial
type: section
title: Editorial hero
summary: An oversized headline across the page, a small tall picture pushed to the right and a ruled strip of facts; asymmetric, not a split or a centred column.
moods: [editorial, calm, crafted]
products: [studio, workshop, magazine, portfolio, restaurant]
tags: [react, tailwind v4, tokens only, hero, asymmetric]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-432)"
preview: assets/preview/sec-hero-editorial.jpg
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-432)"
files:
  - from: recipes/sections/HeroEditorial.tsx
    to: src/sections/HeroEditorial.tsx
---

## Editorial hero

Component `HeroEditorial` in `src/sections/HeroEditorial.tsx`. Every prop has a default (example content): pass your own words, facts and links.
`title` is a list of lines; the last one is set in italic in the accent colour. Pass your own picture as children (a tall crop works best, about 3:4);
the drawn arch is only a stand-in. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, font-display), so changing
the tokens restyles it. Needs the `index.css` token file (asset `tpl-landing-charity`, `tpl-landing-saas` or `tpl-landing-portfolio` ships one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view, keep the headline to two or three short lines, and
check the page at 375 px. Choose it when the brief wants an editorial or crafted feel; for a product with one clear action `HeroSplit` is the plainer choice.
