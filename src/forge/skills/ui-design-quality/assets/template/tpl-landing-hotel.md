---
id: tpl-landing-hotel
type: template
title: "Landing page: small hotel, guesthouse or retreat"
summary: "Terracotta page: picture band, practical facts, rooms as tabs, a gallery, guest words and a booking bar."
moods: [warm, welcoming, calm]
products: [hotel, guesthouse, bed and breakfast, retreat, holiday let, inn]
tags: [react, tailwind v4, page, landing, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-515); fonts from Fontsource, see the OFL texts copied with them"
tested: "NOT RUN YET (written 2026-10-28 without building; the gallery and template tests in tests/test_sections.py must pass before this is relied on)"
files:
  - from: recipes/templates/hotel/App.tsx
    to: src/App.tsx
  - from: recipes/templates/restaurant/index.css
    to: src/index.css
  - from: recipes/sections/NavCentered.tsx
    to: src/sections/NavCentered.tsx
  - from: recipes/sections/HeroStacked.tsx
    to: src/sections/HeroStacked.tsx
  - from: recipes/sections/InfoStrip.tsx
    to: src/sections/InfoStrip.tsx
  - from: recipes/sections/FeaturesTabs.tsx
    to: src/sections/FeaturesTabs.tsx
  - from: recipes/sections/GalleryMosaic.tsx
    to: src/sections/GalleryMosaic.tsx
  - from: recipes/sections/TestimonialColumns.tsx
    to: src/sections/TestimonialColumns.tsx
  - from: recipes/sections/FormBooking.tsx
    to: src/sections/FormBooking.tsx
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

## Landing page: small hotel, guesthouse or retreat

Lora + Nunito, terracotta on cream (the palette of `tpl-landing-restaurant`). Prices and availability must come from the real booking system; put real photographs in the picture band and the gallery.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in `src/sections/`, and the font
files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />` (a Vite + React project with Tailwind v4).

Then adapt: replace every example name, figure and sentence with the product's own, change the palette in the `@theme` block of index.css to the DESIGN.md tokens
(keep the token names), run the audit at 1280 and 375 px and look at the screenshots. Do not ship the example copy.
