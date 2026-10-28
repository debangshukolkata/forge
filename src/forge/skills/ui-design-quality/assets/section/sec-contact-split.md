---
id: sec-contact-split
type: section
title: Contact split
summary: "Address, hours, phone and e-mail as a list on the left and a validated message form on the right."
moods: [practical, open, warm]
products: [shop, studio, clinic, restaurant, school, local business]
tags: [react, tailwind v4, tokens only, form, contact, location, validation]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-contact-split.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/ContactSplit.tsx
    to: src/sections/ContactSplit.tsx
---

## Contact split

Component `ContactSplit` in `src/sections/ContactSplit.tsx`. Every prop has a default (example content): pass your own words and links. `details` is a list of label and value. The form checks the name, the e-mail and a message of at least ten characters, and shows a thank-you. Use it when people also need to find the place; `ContactForm` is the form on its own. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
