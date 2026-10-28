---
id: sec-hero-search
type: section
title: Search hero
summary: "A headline and one large search field with a button, and a line of popular searches under it that fill the field."
moods: [practical, open, helpful]
products: [directory, catalogue, listings, help centre, marketplace]
tags: [react, tailwind v4, tokens only, hero, search, form]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-hero-search.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/HeroSearch.tsx
    to: src/sections/HeroSearch.tsx
---

## Search hero

Component `HeroSearch` in `src/sections/HeroSearch.tsx`. Every prop has a default (example content): pass your own words and links. `onSearch(query)` receives the query; `popular` is a list of terms. A labelled search input in a form with role search. Choose it where the first thing a visitor does is look for something. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
