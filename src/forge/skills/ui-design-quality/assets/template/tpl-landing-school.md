---
id: tpl-landing-school
type: template
title: "Landing page: school, course or training"
summary: "Navy page for a school or training provider: hero with key facts, figures, the timetable, teachers, parents' words and a contact block."
moods: [trustworthy, editorial, calm]
products: [school, course, training, music school, tuition, academy]
tags: [react, tailwind v4, page, landing, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-515); fonts from Fontsource, see the OFL texts copied with them"
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-514, D-515)"
files:
  - from: recipes/templates/school/App.tsx
    to: src/App.tsx
  - from: recipes/templates/about/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/HeroSplit.tsx
    to: src/sections/HeroSplit.tsx
  - from: recipes/sections/ArtTile.tsx
    to: src/sections/ArtTile.tsx
  - from: recipes/sections/FeaturesFigures.tsx
    to: src/sections/FeaturesFigures.tsx
  - from: recipes/sections/ScheduleList.tsx
    to: src/sections/ScheduleList.tsx
  - from: recipes/sections/TeamRoster.tsx
    to: src/sections/TeamRoster.tsx
  - from: recipes/sections/TestimonialColumns.tsx
    to: src/sections/TestimonialColumns.tsx
  - from: recipes/sections/ContactSplit.tsx
    to: src/sections/ContactSplit.tsx
  - from: recipes/sections/FooterColumns.tsx
    to: src/sections/FooterColumns.tsx
  - from: fonts/lora/lora-latin-wght-normal.woff2
    to: public/fonts/lora-latin-wght-normal.woff2
  - from: fonts/lora/lora.css
    to: src/fonts/lora.css
  - from: fonts/lora/lora-OFL.txt
    to: public/fonts/lora-OFL.txt
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
preview: assets/preview/tpl-landing-school-desktop.jpg
---

## Landing page: school, course or training

Lora + Inter, deep navy on cool grey (the palette of `tpl-about-story`). Replace every figure, name, date and quote; only claim results you can show.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in `src/sections/`, and the font
files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />` (a Vite + React project with Tailwind v4).

Then adapt: replace every example name, figure and sentence with the product's own, change the palette in the `@theme` block of index.css to the DESIGN.md tokens
(keep the token names), run the audit at 1280 and 375 px and look at the screenshots. Do not ship the example copy.
