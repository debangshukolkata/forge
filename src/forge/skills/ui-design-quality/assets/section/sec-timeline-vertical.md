---
id: sec-timeline-vertical
type: section
title: Vertical timeline
summary: "Dated entries down the page along a thin line, the year large on the left and the event on the right."
moods: [story, warm, steady]
products: [history, roadmap, programme, about, company, nonprofit]
tags: [react, tailwind v4, tokens only, timeline, history, dates, vertical]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-timeline-vertical.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/TimelineVertical.tsx
    to: src/sections/TimelineVertical.tsx
---

## Vertical timeline

Component `TimelineVertical` in `src/sections/TimelineVertical.tsx`. Every prop has a default (example content): pass your own words and links. `items` is a list of when, title and text (four to eight). Order it newest first or last as the story needs. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
