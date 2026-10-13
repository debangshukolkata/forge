---
id: tpl-landing-portfolio
type: template
title: "Landing page: portfolio"
summary: "Minimal monochrome portfolio: split hero, three selected projects, one quote, a contact form, footer."
moods: [minimal, elegant, quiet]
products: [portfolio, architecture, design, photography, studio]
tags: [react, tailwind v4, page, landing, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-273); fonts from Fontsource, see the OFL texts copied with them"
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-273)"
files:
  - from: recipes/templates/portfolio/App.tsx
    to: src/App.tsx
  - from: recipes/templates/portfolio/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/HeroSplit.tsx
    to: src/sections/HeroSplit.tsx
  - from: recipes/sections/ArtTile.tsx
    to: src/sections/ArtTile.tsx
  - from: recipes/sections/FeaturesAlternating.tsx
    to: src/sections/FeaturesAlternating.tsx
  - from: recipes/sections/TestimonialFeature.tsx
    to: src/sections/TestimonialFeature.tsx
  - from: recipes/sections/ContactForm.tsx
    to: src/sections/ContactForm.tsx
  - from: recipes/sections/FooterColumns.tsx
    to: src/sections/FooterColumns.tsx
  - from: fonts/playfair-display/playfair-display-latin-wght-normal.woff2
    to: public/fonts/playfair-display-latin-wght-normal.woff2
  - from: fonts/playfair-display/playfair-display.css
    to: src/fonts/playfair-display.css
  - from: fonts/playfair-display/playfair-display-OFL.txt
    to: public/fonts/playfair-display-OFL.txt
  - from: fonts/dm-sans/dm-sans-latin-wght-normal.woff2
    to: public/fonts/dm-sans-latin-wght-normal.woff2
  - from: fonts/dm-sans/dm-sans.css
    to: src/fonts/dm-sans.css
  - from: fonts/dm-sans/dm-sans-OFL.txt
    to: public/fonts/dm-sans-OFL.txt
---

## Landing page: portfolio

Playfair Display + DM Sans, near-black accent, square corners, no shadows. Pairs with direction `dir-minimal-monochrome`.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in
`src/sections/`, and the font files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />`
(a Vite + React project; `npm create vite@latest` with the React TypeScript template and `npm i tailwindcss @tailwindcss/vite`, plugin in vite.config).

Then adapt: replace every example text, number and link with the product's own; change the palette in the `@theme` block of index.css to
the DESIGN.md tokens (keep the token names); remove sections the product does not need; run the audit at 1280 and 375 px and look at the
screenshots. Do not ship the example copy.
