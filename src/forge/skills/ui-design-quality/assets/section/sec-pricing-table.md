---
id: sec-pricing-table
type: section
title: Pricing table
summary: "Plans as columns of one real table, features as rows with ticks and rules, the price and a button in the header."
moods: [precise, businesslike, clear]
products: [saas, subscription, software, platform, membership]
tags: [react, tailwind v4, tokens only, pricing, table, comparison, plans]
density: dense
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-pricing-table.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/PricingTable.tsx
    to: src/sections/PricingTable.tsx
---

## Pricing table

Component `PricingTable` in `src/sections/PricingTable.tsx`. Every prop has a default (example content): pass your own words and links. `plans` and `features` (a label and one value per plan: true, false or text). Use it when plans differ in many small ways; `PricingTiers` suits two or three plans that differ in a few. It scrolls sideways inside its own box on a phone. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
