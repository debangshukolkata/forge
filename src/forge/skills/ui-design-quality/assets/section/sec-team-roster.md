---
id: sec-team-roster
type: section
title: Team roster
summary: "People as rows between hairlines: a badge or photo, name and role, a one-line note and a contact link."
moods: [calm, trustworthy, plain]
products: [studio, practice, agency, clinic, firm, school]
tags: [react, tailwind v4, tokens only, team, people, list, about]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-team-roster.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/TeamRoster.tsx
    to: src/sections/TeamRoster.tsx
---

## Team roster

Component `TeamRoster` in `src/sections/TeamRoster.tsx`. Every prop has a default (example content): pass your own words and links. `people` is a list of name, role, note, optional href and photo (a letter badge shows when there is no photo). Quieter and faster to scan than a grid of portrait cards. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
