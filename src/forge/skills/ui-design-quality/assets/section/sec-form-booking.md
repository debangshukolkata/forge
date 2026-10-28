---
id: sec-form-booking
type: section
title: Booking bar
summary: "A compact horizontal form for a date, a time slot and a party size with one button and a confirmation line."
moods: [practical, quick, clear]
products: [restaurant, class, appointment, salon, clinic, venue]
tags: [react, tailwind v4, tokens only, form, booking, date, time, reservation]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-511)"
preview: assets/preview/sec-form-booking.jpg
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshot looked at (tests/test_sections.py, D-511)"
files:
  - from: recipes/sections/FormBooking.tsx
    to: src/sections/FormBooking.tsx
---

## Booking bar

Component `FormBooking` in `src/sections/FormBooking.tsx`. Every prop has a default (example content): pass your own words and links. `slots` lists the times and `maxGuests` the largest party. The date cannot be in the past. `onSubmit({ date, time, guests })`. It uses only the theme token classes of `index.css` (brand-*, ink-*, btn-primary, btn-secondary, eyebrow, field, font-display), so changing the tokens restyles it. Needs the `index.css` token file (the `tpl-landing-*` templates ship one, or copy `recipes/index.css`).

Rules: replace the example copy completely (the audit flags placeholder text), keep one primary button per view and check the page at 375 px.
