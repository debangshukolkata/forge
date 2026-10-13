---
id: tpl-landing-charity
type: template
title: "Landing page: charity or community drive"
summary: "Warm editorial one-page site: hero, stats, steps, testimonial, FAQ, sign-up form, closing band, footer."
moods: [warm, editorial, trustworthy]
products: [charity, health, community, events, education]
tags: [react, tailwind v4, page, landing, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-273); fonts from Fontsource, see the OFL texts copied with them"
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-273)"
files:
  - from: recipes/templates/charity/App.tsx
    to: src/App.tsx
  - from: recipes/templates/charity/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/HeroSplit.tsx
    to: src/sections/HeroSplit.tsx
  - from: recipes/sections/ArtTile.tsx
    to: src/sections/ArtTile.tsx
  - from: recipes/sections/StatsRow.tsx
    to: src/sections/StatsRow.tsx
  - from: recipes/sections/StepsTimeline.tsx
    to: src/sections/StepsTimeline.tsx
  - from: recipes/sections/TestimonialFeature.tsx
    to: src/sections/TestimonialFeature.tsx
  - from: recipes/sections/FaqList.tsx
    to: src/sections/FaqList.tsx
  - from: recipes/sections/ContactForm.tsx
    to: src/sections/ContactForm.tsx
  - from: recipes/sections/CtaBand.tsx
    to: src/sections/CtaBand.tsx
  - from: recipes/sections/FooterColumns.tsx
    to: src/sections/FooterColumns.tsx
  - from: fonts/fraunces/fraunces-latin-wght-normal.woff2
    to: public/fonts/fraunces-latin-wght-normal.woff2
  - from: fonts/fraunces/fraunces.css
    to: src/fonts/fraunces.css
  - from: fonts/fraunces/fraunces-OFL.txt
    to: public/fonts/fraunces-OFL.txt
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
---

## Landing page: charity or community drive

Fraunces + Inter, a deep red accent on warm neutrals. Pairs with direction `dir-soft-editorial`.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in
`src/sections/`, and the font files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />`
(a Vite + React project; `npm create vite@latest` with the React TypeScript template and `npm i tailwindcss @tailwindcss/vite`, plugin in vite.config).

Then adapt: replace every example text, number and link with the product's own; change the palette in the `@theme` block of index.css to
the DESIGN.md tokens (keep the token names); remove sections the product does not need; run the audit at 1280 and 375 px and look at the
screenshots. Do not ship the example copy.
