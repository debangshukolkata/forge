---
id: tpl-landing-restaurant
type: template
title: "Landing page: restaurant or cafe"
summary: "Warm, quiet one-page site: centred navigation, picture band, opening hours, kitchen values, plate gallery, guest quotes, booking bar, centred footer."
moods: [warm, quiet, welcoming]
products: [restaurant, cafe, bakery, bistro, bar, hospitality]
tags: [react, tailwind v4, page, landing, booking, offline fonts]
density: airy
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-514); fonts from Fontsource, see the OFL texts copied with them"
tested: "NOT RUN YET (written 2026-10-28 without building; the gallery and template tests in tests/test_sections.py must pass before this is relied on)"
files:
  - from: recipes/templates/restaurant/App.tsx
    to: src/App.tsx
  - from: recipes/templates/restaurant/index.css
    to: src/index.css
  - from: recipes/sections/NavCentered.tsx
    to: src/sections/NavCentered.tsx
  - from: recipes/sections/HeroStacked.tsx
    to: src/sections/HeroStacked.tsx
  - from: recipes/sections/InfoStrip.tsx
    to: src/sections/InfoStrip.tsx
  - from: recipes/sections/FeaturesIconRow.tsx
    to: src/sections/FeaturesIconRow.tsx
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

## Landing page: restaurant or cafe

Lora + Nunito, terracotta on cream. Pairs with direction `dir-soft-editorial` and palette `pal-warm-trust`.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in
`src/sections/`, and the font files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />`
(a Vite + React project; `npm create vite@latest` with the React TypeScript template and `npm i tailwindcss @tailwindcss/vite`, plugin in vite.config).

Then adapt: replace every example name, hour, dish and quote with the product's own; put real photographs in the picture band (children of `HeroStacked`);
change the palette in the `@theme` block of index.css to the DESIGN.md tokens (keep the token names); run the audit at 1280 and 375 px and look at the
screenshots. Do not ship the example copy.
