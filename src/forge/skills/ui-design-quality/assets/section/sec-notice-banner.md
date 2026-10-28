---
id: sec-notice-banner
type: section
title: Site notice
summary: "A slim dismissible band at the top for something every visitor should know: holiday hours, a price change, an interruption."
moods: [calm, informative, light]
products: [notice, announcement, opening hours, holiday, price change, maintenance]
tags: [react, tailwind v4, tokens only, banner, notice, status, dismiss]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-notice-banner.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/NoticeBanner.tsx
    to: src/sections/NoticeBanner.tsx
---

## Site notice

Component `NoticeBanner` in `src/sections/NoticeBanner.tsx`. Every prop has a default (example content): pass your own words and links. A status region (announced politely, never an alert) with a real Dismiss button; dismissed for the visit only. One notice, one sentence, one optional link. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
