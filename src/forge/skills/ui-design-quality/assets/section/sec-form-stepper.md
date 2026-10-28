---
id: sec-form-stepper
type: section
title: Multi-step form
summary: "Three short steps with a progress line, Back and Next, a check on each step and a review before sending."
moods: [guided, calm, clear]
products: [booking, application, registration, onboarding, survey]
tags: [react, tailwind v4, tokens only, form, steps, wizard, validation, progress]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-form-stepper.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/FormStepper.tsx
    to: src/sections/FormStepper.tsx
---

## Multi-step form

Component `FormStepper` in `src/sections/FormStepper.tsx`. Every prop has a default (example content): pass your own words and links. Change the `steps` list and each step's `fields` (text, e-mail, tel, date, number; required or not; an optional hint). `onSubmit(values)` receives everything. Use it when one long form would put people off. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
