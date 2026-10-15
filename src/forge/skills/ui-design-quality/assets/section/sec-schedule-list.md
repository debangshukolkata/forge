---
id: sec-schedule-list
type: section
title: Schedule with day tabs
summary: "A programme with tabs for the days and a list of sessions with time, speaker and room."
moods: [clear, organised]
products: [events, conferences, festivals]
tags: [react, tailwind v4, tokens only, schedule, tabs, programme]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-385)"
preview: assets/preview/sec-schedule-list.jpg
tested: "built with Vite + Tailwind v4 with the template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px (tests/test_sections.py, D-385)"
files:
  - from: recipes/sections/ScheduleList.tsx
    to: src/sections/ScheduleList.tsx
---

## Schedule with day tabs

Component `ScheduleList` in `src/sections/ScheduleList.tsx`. Every prop has a default (example content): pass your own words, numbers and links. It uses only the theme token classes of `index.css` (brand-*, ink-*, rounded-card, shadow-soft, btn-primary, btn-secondary, card, eyebrow, font-display), so changing the tokens restyles it. The file's first comment says how to use it. Needs the `index.css` token file (any `tpl-*` template ships one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view, and check the page at 375 px.
