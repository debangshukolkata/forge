---
id: sec-hero-numbers
type: section
title: Numbers hero
summary: "The headline on the left and three large figures on the right, each with a label, between hairlines."
moods: [precise, trustworthy, serious]
products: [clinic, report, fintech, nonprofit, research, service]
tags: [react, tailwind v4, tokens only, hero, figures, proof]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-hero-numbers.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/HeroNumbers.tsx
    to: src/sections/HeroNumbers.tsx
---

## Numbers hero

Component `HeroNumbers` in `src/sections/HeroNumbers.tsx`. Every prop has a default (example content): pass your own words and links. `figures` is a list of value and label; use real, specific numbers (the audit flags placeholder text). Choose it when the claim can be proven with numbers. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
