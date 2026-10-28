---
id: tpl-feedback-page
type: template
title: "Feedback page"
summary: "A one-to-five rating and a comment first, then what other guests said, with a centred navigation and footer."
moods: [warm, friendly, simple]
products: [feedback, review, survey, restaurant, event, support]
tags: [react, tailwind v4, page, feedback, form, offline fonts]
density: airy
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-514); uses the restaurant palette and fonts; fonts from Fontsource, see the OFL texts copied with them"
tested: "NOT RUN YET (written 2026-10-28 without building; the gallery and template tests in tests/test_sections.py must pass before this is relied on)"
files:
  - from: recipes/templates/feedback/App.tsx
    to: src/App.tsx
  - from: recipes/templates/restaurant/index.css
    to: src/index.css
  - from: recipes/sections/NavCentered.tsx
    to: src/sections/NavCentered.tsx
  - from: recipes/sections/FormFeedback.tsx
    to: src/sections/FormFeedback.tsx
  - from: recipes/sections/TestimonialColumns.tsx
    to: src/sections/TestimonialColumns.tsx
  - from: recipes/sections/FooterCentered.tsx
    to: src/sections/FooterCentered.tsx
  - from: fonts/lora/lora-latin-wght-normal.woff2
    to: public/fonts/lora-latin-wght-normal.woff2
  - from: fonts/lora/lora.css
    to: src/fonts/lora.css
  - from: fonts/lora/lora-OFL.txt
    to: public/fonts/lora-OFL.txt
  - from: fonts/nunito/nunito-latin-wght-normal.woff2
    to: public/fonts/nunito-latin-wght-normal.woff2
  - from: fonts/nunito/nunito.css
    to: src/fonts/nunito.css
  - from: fonts/nunito/nunito-OFL.txt
    to: public/fonts/nunito-OFL.txt
---

## Feedback page

Lora + Nunito, terracotta on cream (the palette of `tpl-landing-restaurant`).

Copies a complete page into the project: `src/App.tsx`, `src/index.css`, the sections and the font files with their licence texts. `src/main.tsx` should
import `./index.css` and render `<App />` (a Vite + React project with Tailwind v4).

Then adapt: send `FormFeedback`'s `onSubmit` to the real back end, replace the business name, and show only comments people have given permission to
publish (or remove `TestimonialColumns`). Run the audit at 1280 and 375 px and look at the screenshots.
