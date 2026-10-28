---
id: sec-features-figures
type: section
title: Features with figures
summary: "Two to four points that each lead with a large figure or short word, then a title and one sentence, between hairlines."
moods: [proof, precise, steady]
products: [service, agency, consultancy, clinic, supplier, school]
tags: [react, tailwind v4, tokens only, features, figures, numbers, proof]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-features-figures.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/FeaturesFigures.tsx
    to: src/sections/FeaturesFigures.tsx
---

## Features with figures

Component `FeaturesFigures` in `src/sections/FeaturesFigures.tsx`. Every prop has a default (example content): pass your own words and links. `items` is a list of figure, title and text. Use it only when each point can be backed by a real figure; otherwise use `FeaturesRuled` or `FeaturesIconRow`. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
