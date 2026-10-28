---
id: tpl-about-story
type: template
title: "About page: company or family story"
summary: "Editorial opening, a dated timeline, the principles, the people, one long quote and a closing invitation, in deep navy."
moods: [editorial, trustworthy, heritage]
products: [about, company, family business, workshop, firm, charity history]
tags: [react, tailwind v4, page, about, timeline, offline fonts]
density: airy
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-514); fonts from Fontsource, see the OFL texts copied with them"
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-514, D-515)"
files:
  - from: recipes/templates/about/App.tsx
    to: src/App.tsx
  - from: recipes/templates/about/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/HeroEditorial.tsx
    to: src/sections/HeroEditorial.tsx
  - from: recipes/sections/TimelineVertical.tsx
    to: src/sections/TimelineVertical.tsx
  - from: recipes/sections/FeaturesNumbered.tsx
    to: src/sections/FeaturesNumbered.tsx
  - from: recipes/sections/TeamRoster.tsx
    to: src/sections/TeamRoster.tsx
  - from: recipes/sections/TestimonialFeature.tsx
    to: src/sections/TestimonialFeature.tsx
  - from: recipes/sections/CtaBand.tsx
    to: src/sections/CtaBand.tsx
  - from: recipes/sections/FooterMinimal.tsx
    to: src/sections/FooterMinimal.tsx
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
preview: assets/preview/tpl-about-story-desktop.jpg
---

## About page: company or family story

Lora + Inter, deep navy on cool grey. Pairs with direction `dir-soft-editorial`.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in
`src/sections/`, and the font files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />`
(a Vite + React project; `npm create vite@latest` with the React TypeScript template and `npm i tailwindcss @tailwindcss/vite`, plugin in vite.config).

Then adapt: replace every date, name and claim with true ones; **a history page loses all credit if one date is wrong, so check each date with the
owner**. Change the palette in the `@theme` block of index.css to the DESIGN.md tokens (keep the token names); run the audit at 1280 and 375 px and
look at the screenshots. Do not ship the example copy.
