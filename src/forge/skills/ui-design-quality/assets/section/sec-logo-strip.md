---
id: sec-logo-strip
type: section
title: Trusted-by strip
summary: A row of customer names (or logos) under a short label.
moods: [clean, trustworthy]
products: [saas, b2b, agencies]
tags: [react, tailwind v4, tokens only, social proof]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-273)"
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-273)"
files:
  - from: recipes/sections/LogoStrip.tsx
    to: src/sections/LogoStrip.tsx
---

## Trusted-by strip

Component `LogoStrip` in `src/sections/LogoStrip.tsx`. Every prop has a default (example content): pass your own words, numbers and links.
It uses only the theme token classes of `index.css` (brand-*, ink-*, rounded-card, shadow-soft, btn-primary, btn-secondary, card, eyebrow,
field, font-display), so changing the tokens restyles it. The file's first comment says how to use it. Needs the `index.css` token file
(asset `tpl-landing-charity`, `tpl-landing-saas` or `tpl-landing-portfolio` ships one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view, and check the page at 375 px.
