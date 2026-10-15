---
id: sec-speaker-grid
type: section
title: Speaker or team grid
summary: "People cards with an initials avatar, name, role and one line; two columns on a phone, four on desktop."
moods: [friendly, clean]
products: [events, teams, about pages]
tags: [react, tailwind v4, tokens only, people, speakers, team]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-385)"
tested: "built with Vite + Tailwind v4 with the template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px (tests/test_sections.py, D-385)"
files:
  - from: recipes/sections/SpeakerGrid.tsx
    to: src/sections/SpeakerGrid.tsx
---

## Speaker or team grid

Component `SpeakerGrid` in `src/sections/SpeakerGrid.tsx`. Every prop has a default (example content): pass your own words, numbers and links. It uses only the theme token classes of `index.css` (brand-*, ink-*, rounded-card, shadow-soft, btn-primary, btn-secondary, card, eyebrow, font-display), so changing the tokens restyles it. The file's first comment says how to use it. Needs the `index.css` token file (any `tpl-*` template ships one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view, and check the page at 375 px.
