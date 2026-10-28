---
id: tpl-landing-agency
type: template
title: "Landing page: design or marketing agency"
summary: "Loud poster hero in vermilion, a numbered way of working, a work gallery, one big client quote, the people and a contact block."
moods: [bold, loud, confident]
products: [agency, studio, design, marketing, consultancy, creative]
tags: [react, tailwind v4, page, landing, poster, offline fonts]
density: airy
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-514); fonts from Fontsource, see the OFL texts copied with them"
tested: "NOT RUN YET (written 2026-10-28 without building; the gallery and template tests in tests/test_sections.py must pass before this is relied on)"
files:
  - from: recipes/templates/agency/App.tsx
    to: src/App.tsx
  - from: recipes/templates/agency/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/HeroPoster.tsx
    to: src/sections/HeroPoster.tsx
  - from: recipes/sections/FeaturesNumbered.tsx
    to: src/sections/FeaturesNumbered.tsx
  - from: recipes/sections/GalleryMosaic.tsx
    to: src/sections/GalleryMosaic.tsx
  - from: recipes/sections/TestimonialFeature.tsx
    to: src/sections/TestimonialFeature.tsx
  - from: recipes/sections/TeamRoster.tsx
    to: src/sections/TeamRoster.tsx
  - from: recipes/sections/ContactSplit.tsx
    to: src/sections/ContactSplit.tsx
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
---

## Landing page: design or marketing agency

Archivo + DM Sans, vermilion on warm grey. Pairs with direction `dir-bold-poster`.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in
`src/sections/`, and the font files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />`
(a Vite + React project; `npm create vite@latest` with the React TypeScript template and `npm i tailwindcss @tailwindcss/vite`, plugin in vite.config).

Then adapt: replace every name, project and quote with true ones (client quotes need the client's permission) and put real project pictures into the gallery tiles.
Keep the poster headline to one to three words. Change the palette in the `@theme` block of index.css to the DESIGN.md tokens (keep the token names; white
text sits on the brand colour, so keep it dark enough); run the audit at 1280 and 375 px and look at the screenshots.
