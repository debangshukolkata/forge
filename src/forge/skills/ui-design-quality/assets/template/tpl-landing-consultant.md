---
id: tpl-landing-consultant
type: template
title: "Landing page: consultant, coach or small practice"
summary: "Green page led by one clear statement, a numbered way of working, figures, one client quote, questions and a contact block."
moods: [personal, plain, confident]
products: [consultant, coach, freelancer, practice, adviser, writer]
tags: [react, tailwind v4, page, landing, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-515); fonts from Fontsource, see the OFL texts copied with them"
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-514, D-515)"
files:
  - from: recipes/templates/consultant/App.tsx
    to: src/App.tsx
  - from: recipes/templates/directory/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/HeroQuote.tsx
    to: src/sections/HeroQuote.tsx
  - from: recipes/sections/FeaturesNumbered.tsx
    to: src/sections/FeaturesNumbered.tsx
  - from: recipes/sections/FeaturesFigures.tsx
    to: src/sections/FeaturesFigures.tsx
  - from: recipes/sections/TestimonialFeature.tsx
    to: src/sections/TestimonialFeature.tsx
  - from: recipes/sections/FaqList.tsx
    to: src/sections/FaqList.tsx
  - from: recipes/sections/ContactSplit.tsx
    to: src/sections/ContactSplit.tsx
  - from: recipes/sections/FooterMinimal.tsx
    to: src/sections/FooterMinimal.tsx
  - from: fonts/nunito/nunito-latin-wght-normal.woff2
    to: public/fonts/nunito-latin-wght-normal.woff2
  - from: fonts/nunito/nunito.css
    to: src/fonts/nunito.css
  - from: fonts/nunito/nunito-OFL.txt
    to: public/fonts/nunito-OFL.txt
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
preview: assets/preview/tpl-landing-consultant-desktop.jpg
---

## Landing page: consultant, coach or small practice

Nunito + Inter, forest green on warm grey (the palette of `tpl-directory-search`). Every claim and figure must be true; a client quote needs the client's permission.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in `src/sections/`, and the font
files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />` (a Vite + React project with Tailwind v4).

Then adapt: replace every example name, figure and sentence with the product's own, change the palette in the `@theme` block of index.css to the DESIGN.md tokens
(keep the token names), run the audit at 1280 and 375 px and look at the screenshots. Do not ship the example copy.
