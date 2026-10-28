---
id: tpl-landing-clinic
type: template
title: "Landing page: clinic or health practice"
summary: "Calm teal page: a hero that proves its claim with figures, services, the people, patient quotes, questions, and a contact block with address and hours."
moods: [calm, trustworthy, clear]
products: [clinic, health, practice, dentist, therapy, wellbeing]
tags: [react, tailwind v4, page, landing, trust, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-514); fonts from Fontsource, see the OFL texts copied with them"
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-514, D-515)"
files:
  - from: recipes/templates/clinic/App.tsx
    to: src/App.tsx
  - from: recipes/templates/clinic/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/HeroNumbers.tsx
    to: src/sections/HeroNumbers.tsx
  - from: recipes/sections/FeaturesIconRow.tsx
    to: src/sections/FeaturesIconRow.tsx
  - from: recipes/sections/TeamRoster.tsx
    to: src/sections/TeamRoster.tsx
  - from: recipes/sections/TestimonialColumns.tsx
    to: src/sections/TestimonialColumns.tsx
  - from: recipes/sections/FaqList.tsx
    to: src/sections/FaqList.tsx
  - from: recipes/sections/ContactSplit.tsx
    to: src/sections/ContactSplit.tsx
  - from: recipes/sections/FooterMinimal.tsx
    to: src/sections/FooterMinimal.tsx
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans-latin-wght-normal.woff2
    to: public/fonts/plus-jakarta-sans-latin-wght-normal.woff2
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans.css
    to: src/fonts/plus-jakarta-sans.css
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans-OFL.txt
    to: public/fonts/plus-jakarta-sans-OFL.txt
  - from: fonts/manrope/manrope-latin-wght-normal.woff2
    to: public/fonts/manrope-latin-wght-normal.woff2
  - from: fonts/manrope/manrope.css
    to: src/fonts/manrope.css
  - from: fonts/manrope/manrope-OFL.txt
    to: public/fonts/manrope-OFL.txt
preview: assets/preview/tpl-landing-clinic-desktop.jpg
---

## Landing page: clinic or health practice

Plus Jakarta Sans + Manrope, teal on cool grey. Pairs with direction `dir-clean-product` and palette `pal-calm-clinical`.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in
`src/sections/`, and the font files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />`
(a Vite + React project; `npm create vite@latest` with the React TypeScript template and `npm i tailwindcss @tailwindcss/vite`, plugin in vite.config).

Then adapt: replace every figure, name, service and answer with the practice's own. **Every number on a health page must be one the practice can
stand behind; never invent a clinical claim, a waiting time or a patient quote.** Change the palette in the `@theme` block of index.css to the DESIGN.md
tokens (keep the token names); run the audit at 1280 and 375 px and look at the screenshots. Do not ship the example copy.
