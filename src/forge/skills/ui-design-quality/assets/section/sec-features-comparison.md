---
id: sec-features-comparison
type: section
title: Before and after
summary: "Two columns of short lines, the old way struck through in grey and the new way in full colour with a tick."
moods: [clear, persuasive, plain]
products: [saas, service, booking, migration, upgrade, tool]
tags: [react, tailwind v4, tokens only, features, comparison, before after]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-features-comparison.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/FeaturesComparison.tsx
    to: src/sections/FeaturesComparison.tsx
---

## Before and after

Component `FeaturesComparison` in `src/sections/FeaturesComparison.tsx`. Every prop has a default (example content): pass your own words and links. `before` and `after` each have a heading and three to six lines of the same length. Choose it where the benefit is a contrast (a week against an hour). It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
