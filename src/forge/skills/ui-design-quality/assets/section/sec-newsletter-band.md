---
id: sec-newsletter-band
type: section
title: Newsletter band
summary: "A slim full-width band with one sentence on the left and an inline e-mail field on the right; sits above a footer."
moods: [light, friendly, plain]
products: [newsletter, blog, shop, studio, community]
tags: [react, tailwind v4, tokens only, form, e-mail, band, validation]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-newsletter-band.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/NewsletterBand.tsx
    to: src/sections/NewsletterBand.tsx
---

## Newsletter band

Component `NewsletterBand` in `src/sections/NewsletterBand.tsx`. Every prop has a default (example content): pass your own words and links. A real labelled input that validates on submit; `onSubmit(email)` receives the address. Put it between the last section and the footer. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
