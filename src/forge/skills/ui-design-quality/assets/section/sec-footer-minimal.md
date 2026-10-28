---
id: sec-footer-minimal
type: section
title: Minimal footer
summary: "One line: brand and legal text on the left, a few plain links on the right; nothing else."
moods: [quiet, light, plain]
products: [one-page site, portfolio, landing page, short page]
tags: [react, tailwind v4, tokens only, footer, minimal, links]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-footer-minimal.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/FooterMinimal.tsx
    to: src/sections/FooterMinimal.tsx
---

## Minimal footer

Component `FooterMinimal` in `src/sections/FooterMinimal.tsx`. Every prop has a default (example content): pass your own words and links. `links` is a short list (three or four). Choose it where a column footer would be heavier than the page above it. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
