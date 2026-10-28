---
id: sec-hero-signup
type: section
title: Sign-up hero
summary: "A centred headline, one sentence and an inline e-mail field with a button; the single action happens in the first view."
moods: [focused, modern, plain]
products: [waiting list, newsletter, saas, launch, app]
tags: [react, tailwind v4, tokens only, hero, form, e-mail, validation]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-hero-signup.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/HeroSignup.tsx
    to: src/sections/HeroSignup.tsx
---

## Sign-up hero

Component `HeroSignup` in `src/sections/HeroSignup.tsx`. Every prop has a default (example content): pass your own words and links. A real labelled input that validates on submit; `onSubmit(email)` receives the address. Choose it for a pre-launch or waiting-list page with one goal. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
