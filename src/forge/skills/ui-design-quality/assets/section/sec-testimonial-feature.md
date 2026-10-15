---
id: sec-testimonial-feature
type: section
title: "Testimonial: one big quote"
summary: A large quote on a tinted band with name and role.
moods: [warm, editorial, trustworthy]
products: [charity, portfolio, services]
tags: [react, tailwind v4, tokens only, social proof]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-273)"
preview: assets/preview/sec-testimonial-feature.jpg
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-273)"
files:
  - from: recipes/sections/TestimonialFeature.tsx
    to: src/sections/TestimonialFeature.tsx
---

## Testimonial: one big quote

Component `TestimonialFeature` in `src/sections/TestimonialFeature.tsx`. Every prop has a default (example content): pass your own words, numbers and links.
It uses only the theme token classes of `index.css` (brand-*, ink-*, rounded-card, shadow-soft, btn-primary, btn-secondary, card, eyebrow,
field, font-display), so changing the tokens restyles it. The file's first comment says how to use it. Needs the `index.css` token file
(asset `tpl-landing-charity`, `tpl-landing-saas` or `tpl-landing-portfolio` ships one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view, and check the page at 375 px.
