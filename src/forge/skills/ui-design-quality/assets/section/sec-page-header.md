---
id: sec-page-header
type: section
title: Inner page header
summary: "Breadcrumbs, the page's own h1, a one-sentence introduction and an optional line of facts such as the updated date."
moods: [clear, orderly, plain]
products: [service page, article, policy, product page, documentation, inner page]
tags: [react, tailwind v4, tokens only, header, breadcrumb, title, navigation]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-page-header.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/PageHeader.tsx
    to: src/sections/PageHeader.tsx
---

## Inner page header

Component `PageHeader` in `src/sections/PageHeader.tsx`. Every prop has a default (example content): pass your own words and links. `crumbs` ends with the current page (no href), announced as the current page. Use it at the top of any page that is not the home page. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
