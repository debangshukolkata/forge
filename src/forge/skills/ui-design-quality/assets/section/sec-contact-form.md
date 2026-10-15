---
id: sec-contact-form
type: section
title: Contact or sign-up form
summary: "Labelled fields, inline validation messages, a sending state and a success message."
moods: [clean, friendly]
products: [sign-up, contact, booking]
tags: [react, tailwind v4, tokens only, form]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-273)"
preview: assets/preview/sec-contact-form.jpg
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-273)"
files:
  - from: recipes/sections/ContactForm.tsx
    to: src/sections/ContactForm.tsx
---

## Contact or sign-up form

Component `ContactForm` in `src/sections/ContactForm.tsx`. Every prop has a default (example content): pass your own words, numbers and links.
It uses only the theme token classes of `index.css` (brand-*, ink-*, rounded-card, shadow-soft, btn-primary, btn-secondary, card, eyebrow,
field, font-display), so changing the tokens restyles it. The file's first comment says how to use it. Needs the `index.css` token file
(asset `tpl-landing-charity`, `tpl-landing-saas` or `tpl-landing-portfolio` ships one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view, and check the page at 375 px.
