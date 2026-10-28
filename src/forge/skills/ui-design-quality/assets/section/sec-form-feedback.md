---
id: sec-form-feedback
type: section
title: Feedback form
summary: "A one-to-five rating as real radio buttons, a comment box with a character count and an optional reply e-mail."
moods: [friendly, simple, open]
products: [feedback, review, survey, support, restaurant, event]
tags: [react, tailwind v4, tokens only, form, rating, radio, comment, validation]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-form-feedback.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/FormFeedback.tsx
    to: src/sections/FormFeedback.tsx
---

## Feedback form

Component `FormFeedback` in `src/sections/FormFeedback.tsx`. Every prop has a default (example content): pass your own words and links. `onSubmit({ rating, comment, email })`. The rating is required, the rest optional. Shows a thank-you after sending. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
