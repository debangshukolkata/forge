---
id: tpl-landing-fitness
type: template
title: "Landing page: gym, studio or sports club"
summary: "Vermilion poster hero, what makes the place different, the class timetable, membership plans, questions and a trial-class booking bar."
moods: [energetic, bold, friendly]
products: [gym, fitness, studio, sports club, yoga, classes]
tags: [react, tailwind v4, page, landing, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-515); fonts from Fontsource, see the OFL texts copied with them"
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-514, D-515)"
files:
  - from: recipes/templates/fitness/App.tsx
    to: src/App.tsx
  - from: recipes/templates/agency/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/HeroPoster.tsx
    to: src/sections/HeroPoster.tsx
  - from: recipes/sections/FeaturesIconRow.tsx
    to: src/sections/FeaturesIconRow.tsx
  - from: recipes/sections/ScheduleList.tsx
    to: src/sections/ScheduleList.tsx
  - from: recipes/sections/PricingTable.tsx
    to: src/sections/PricingTable.tsx
  - from: recipes/sections/FaqList.tsx
    to: src/sections/FaqList.tsx
  - from: recipes/sections/FormBooking.tsx
    to: src/sections/FormBooking.tsx
  - from: recipes/sections/FooterCentered.tsx
    to: src/sections/FooterCentered.tsx
  - from: fonts/archivo/archivo-latin-wght-normal.woff2
    to: public/fonts/archivo-latin-wght-normal.woff2
  - from: fonts/archivo/archivo.css
    to: src/fonts/archivo.css
  - from: fonts/archivo/archivo-OFL.txt
    to: public/fonts/archivo-OFL.txt
  - from: fonts/dm-sans/dm-sans-latin-wght-normal.woff2
    to: public/fonts/dm-sans-latin-wght-normal.woff2
  - from: fonts/dm-sans/dm-sans.css
    to: src/fonts/dm-sans.css
  - from: fonts/dm-sans/dm-sans-OFL.txt
    to: public/fonts/dm-sans-OFL.txt
preview: assets/preview/tpl-landing-fitness-desktop.jpg
---

## Landing page: gym, studio or sports club

Archivo + DM Sans, vermilion on warm grey (the palette of `tpl-landing-agency`). Replace every class, time and price; keep any health claim to what the studio can stand behind.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in `src/sections/`, and the font
files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />` (a Vite + React project with Tailwind v4).

Then adapt: replace every example name, figure and sentence with the product's own, change the palette in the `@theme` block of index.css to the DESIGN.md tokens
(keep the token names), run the audit at 1280 and 375 px and look at the screenshots. Do not ship the example copy.
