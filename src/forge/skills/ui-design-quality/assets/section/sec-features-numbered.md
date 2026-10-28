---
id: sec-features-numbered
type: section
title: Numbered features
summary: "A short intro that stays in view on the left and a long column of numbered points on the right, each with a large numeral."
moods: [editorial, ordered, calm]
products: [method, process, principles, agency, consultancy, course]
tags: [react, tailwind v4, tokens only, features, numbered, sticky, list]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-features-numbered.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/FeaturesNumbered.tsx
    to: src/sections/FeaturesNumbered.tsx
---

## Numbered features

Component `FeaturesNumbered` in `src/sections/FeaturesNumbered.tsx`. Every prop has a default (example content): pass your own words and links. `items` is a list of title and text (four to eight). The intro is sticky on desktop and stacks on a phone. Choose it for a method that is read in order. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
