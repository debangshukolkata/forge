---
id: tpl-directory-search
type: template
title: "Directory or help centre"
summary: "A big search field first, then category tiles, figures that show the listings are kept current, how they are checked, questions and a newsletter band."
moods: [practical, open, helpful]
products: [directory, help centre, listings, community, catalogue, services]
tags: [react, tailwind v4, page, landing, search, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-514); fonts from Fontsource, see the OFL texts copied with them"
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-514, D-515)"
files:
  - from: recipes/templates/directory/App.tsx
    to: src/App.tsx
  - from: recipes/templates/directory/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/HeroSearch.tsx
    to: src/sections/HeroSearch.tsx
  - from: recipes/sections/CategoryTiles.tsx
    to: src/sections/CategoryTiles.tsx
  - from: recipes/sections/StatsRow.tsx
    to: src/sections/StatsRow.tsx
  - from: recipes/sections/FeaturesNumbered.tsx
    to: src/sections/FeaturesNumbered.tsx
  - from: recipes/sections/FaqList.tsx
    to: src/sections/FaqList.tsx
  - from: recipes/sections/NewsletterBand.tsx
    to: src/sections/NewsletterBand.tsx
  - from: recipes/sections/FooterColumns.tsx
    to: src/sections/FooterColumns.tsx
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
preview: assets/preview/tpl-directory-search-desktop.jpg
---

## Directory or help centre

Nunito + Inter, forest green on warm grey. Pairs with palette `pal-fresh-and-friendly`.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in
`src/sections/`, and the font files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />`
(a Vite + React project; `npm create vite@latest` with the React TypeScript template and `npm i tailwindcss @tailwindcss/vite`, plugin in vite.config).

Then adapt: connect `HeroSearch`'s `onSearch` to the real search; replace every category, figure and answer with the product's own (the figures
must be real: a directory that says it is checked every six months must be). Change the palette in the `@theme` block of index.css to the DESIGN.md tokens
(keep the token names); run the audit at 1280 and 375 px and look at the screenshots.
