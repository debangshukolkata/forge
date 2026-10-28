---
id: sec-download-list
type: section
title: Download list
summary: "Documents as rows with title, one-line description, file type and size, and a download link that says what it is."
moods: [practical, plain, tidy]
products: [forms, reports, price list, policy, documents, charity, council, school]
tags: [react, tailwind v4, tokens only, downloads, documents, files, list]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-download-list.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/DownloadList.tsx
    to: src/sections/DownloadList.tsx
---

## Download list

Component `DownloadList` in `src/sections/DownloadList.tsx`. Every prop has a default (example content): pass your own words and links. `items` is a list of title, text, type, size and href; give the real type and size. The link text says what the file is (Download PDF). It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
