---
id: tpl-shop-craft
type: template
title: "Shop: craft goods"
summary: "A small-shop storefront: hero, category tiles, product grid, facts, a customer quote, delivery questions, newsletter band, footer."
moods: [warm, crafted, trustworthy]
products: [shop, e-commerce, handmade, retail]
tags: [react, tailwind v4, page, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-385); fonts from Fontsource, see the OFL texts copied with them"
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-385)"
files:
  - from: recipes/templates/shop/App.tsx
    to: src/App.tsx
  - from: recipes/templates/shop/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/HeroSplit.tsx
    to: src/sections/HeroSplit.tsx
  - from: recipes/sections/ArtTile.tsx
    to: src/sections/ArtTile.tsx
  - from: recipes/sections/CategoryTiles.tsx
    to: src/sections/CategoryTiles.tsx
  - from: recipes/sections/ProductGrid.tsx
    to: src/sections/ProductGrid.tsx
  - from: recipes/sections/StatsRow.tsx
    to: src/sections/StatsRow.tsx
  - from: recipes/sections/TestimonialFeature.tsx
    to: src/sections/TestimonialFeature.tsx
  - from: recipes/sections/FaqList.tsx
    to: src/sections/FaqList.tsx
  - from: recipes/sections/CtaBand.tsx
    to: src/sections/CtaBand.tsx
  - from: recipes/sections/FooterColumns.tsx
    to: src/sections/FooterColumns.tsx
  - from: fonts/playfair-display/playfair-display-latin-wght-normal.woff2
    to: public/fonts/playfair-display-latin-wght-normal.woff2
  - from: fonts/playfair-display/playfair-display.css
    to: src/fonts/playfair-display.css
  - from: fonts/playfair-display/playfair-display-OFL.txt
    to: public/fonts/playfair-display-OFL.txt
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans-latin-wght-normal.woff2
    to: public/fonts/plus-jakarta-sans-latin-wght-normal.woff2
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans.css
    to: src/fonts/plus-jakarta-sans.css
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans-OFL.txt
    to: public/fonts/plus-jakarta-sans-OFL.txt
---

## Shop: craft goods

Playfair Display + Plus Jakarta Sans, sage green on warm stone. For small shops of handmade or specialist goods.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in
`src/sections/`, and the font files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />`
(a Vite + React project; `npm create vite@latest` with the React TypeScript template and `npm i tailwindcss @tailwindcss/vite`, plugin in vite.config).

Then adapt: replace every example text, number and link with the product's own; change the palette in the `@theme` block of index.css to
the DESIGN.md tokens (keep the token names); remove sections the product does not need; run the audit at 1280 and 375 px and look at the
screenshots. Do not ship the example copy.
