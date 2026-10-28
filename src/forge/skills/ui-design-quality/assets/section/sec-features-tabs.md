---
id: sec-features-tabs
type: section
title: Tabbed features
summary: "A row of tabs with one panel of text under it; arrow keys, Home and End move between the tabs and the selected one is announced."
moods: [organised, practical, clean]
products: [studio, school, product, services, platform]
tags: [react, tailwind v4, tokens only, features, tabs, accessible, interactive]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-features-tabs.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/FeaturesTabs.tsx
    to: src/sections/FeaturesTabs.tsx
---

## Tabbed features

Component `FeaturesTabs` in `src/sections/FeaturesTabs.tsx`. Every prop has a default (example content): pass your own words and links. `tabs` is a list of label, title, text and optional points (three to five). Choose it when several features need a paragraph each and one place. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
