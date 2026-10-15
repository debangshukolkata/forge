---
id: sec-docs-shell
type: section
title: Documentation shell
summary: "A documentation page: sticky navigation, article with code block and note, and an On this page list."
moods: [technical, calm]
products: [documentation, developer tools, help centre]
tags: [react, tailwind v4, tokens only, docs, sidebar, code]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-385)"
tested: "built with Vite + Tailwind v4 with the template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px (tests/test_sections.py, D-385)"
files:
  - from: recipes/sections/DocsShell.tsx
    to: src/sections/DocsShell.tsx
---

## Documentation shell

Component `DocsShell` in `src/sections/DocsShell.tsx`. Every prop has a default (example content): pass your own words, numbers and links. It uses only the theme token classes of `index.css` (brand-*, ink-*, rounded-card, shadow-soft, btn-primary, btn-secondary, card, eyebrow, font-display), so changing the tokens restyles it. The file's first comment says how to use it. Needs the `index.css` token file (any `tpl-*` template ships one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view, and check the page at 375 px.
