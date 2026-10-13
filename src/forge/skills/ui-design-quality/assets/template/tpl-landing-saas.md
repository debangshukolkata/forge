---
id: tpl-landing-saas
type: template
title: "Landing page: software product"
summary: "Clean light product site: centred hero with a visual, logo strip, bento features, stats, pricing, FAQ, closing band, footer."
moods: [clean, modern, polished]
products: [saas, startups, apps, b2b, fintech]
tags: [react, tailwind v4, page, landing, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-273); fonts from Fontsource, see the OFL texts copied with them"
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-273)"
files:
  - from: recipes/templates/saas/App.tsx
    to: src/App.tsx
  - from: recipes/templates/saas/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/HeroCentered.tsx
    to: src/sections/HeroCentered.tsx
  - from: recipes/sections/ArtTile.tsx
    to: src/sections/ArtTile.tsx
  - from: recipes/sections/LogoStrip.tsx
    to: src/sections/LogoStrip.tsx
  - from: recipes/sections/FeaturesBento.tsx
    to: src/sections/FeaturesBento.tsx
  - from: recipes/sections/StatsRow.tsx
    to: src/sections/StatsRow.tsx
  - from: recipes/sections/PricingTiers.tsx
    to: src/sections/PricingTiers.tsx
  - from: recipes/sections/FaqList.tsx
    to: src/sections/FaqList.tsx
  - from: recipes/sections/CtaBand.tsx
    to: src/sections/CtaBand.tsx
  - from: recipes/sections/FooterColumns.tsx
    to: src/sections/FooterColumns.tsx
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans-latin-wght-normal.woff2
    to: public/fonts/plus-jakarta-sans-latin-wght-normal.woff2
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans.css
    to: src/fonts/plus-jakarta-sans.css
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans-OFL.txt
    to: public/fonts/plus-jakarta-sans-OFL.txt
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
---

## Landing page: software product

Plus Jakarta Sans + Inter, an indigo accent on cool slate neutrals. Pairs with direction `dir-clean-product`.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in
`src/sections/`, and the font files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />`
(a Vite + React project; `npm create vite@latest` with the React TypeScript template and `npm i tailwindcss @tailwindcss/vite`, plugin in vite.config).

Then adapt: replace every example text, number and link with the product's own; change the palette in the `@theme` block of index.css to
the DESIGN.md tokens (keep the token names); remove sections the product does not need; run the audit at 1280 and 375 px and look at the
screenshots. Do not ship the example copy.
