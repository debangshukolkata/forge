---
id: sec-hero-quote
type: section
title: Quote hero
summary: "One large statement as the headline with who said it underneath, a short rule above and one button."
moods: [personal, confident, plain]
products: [consultant, coach, writer, practice, small firm, freelancer]
tags: [react, tailwind v4, tokens only, hero, quote, statement, big type]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-hero-quote.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/HeroQuote.tsx
    to: src/sections/HeroQuote.tsx
---

## Quote hero

Component `HeroQuote` in `src/sections/HeroQuote.tsx`. Every prop has a default (example content): pass your own words and links. `quote` is one or two sentences you would stand behind; a quote from a real client needs their permission. Choose it when a person's view is the product. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
