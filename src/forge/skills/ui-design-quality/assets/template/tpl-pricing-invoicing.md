---
id: tpl-pricing-invoicing
type: template
title: "Pricing page: plans, proof and billing questions"
summary: "A pricing page: top bar, centred hero, customer names, three plan cards with one featured, key numbers, billing FAQ, closing band, footer."
moods: [clear, confident, warm]
products: [pricing page, subscription, invoicing, saas plans]
tags: [react, tailwind v4, page, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-389); fonts from Fontsource, see the OFL texts copied with them"
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-389)"
files:
  - from: recipes/templates/pricing/App.tsx
    to: src/App.tsx
  - from: recipes/templates/pricing/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/HeroCentered.tsx
    to: src/sections/HeroCentered.tsx
  - from: recipes/sections/LogoStrip.tsx
    to: src/sections/LogoStrip.tsx
  - from: recipes/sections/PricingTiers.tsx
    to: src/sections/PricingTiers.tsx
  - from: recipes/sections/StatsRow.tsx
    to: src/sections/StatsRow.tsx
  - from: recipes/sections/FaqList.tsx
    to: src/sections/FaqList.tsx
  - from: recipes/sections/CtaBand.tsx
    to: src/sections/CtaBand.tsx
  - from: recipes/sections/FooterColumns.tsx
    to: src/sections/FooterColumns.tsx
  - from: fonts/manrope/manrope-latin-wght-normal.woff2
    to: public/fonts/manrope-latin-wght-normal.woff2
  - from: fonts/manrope/manrope.css
    to: src/fonts/manrope.css
  - from: fonts/manrope/manrope-OFL.txt
    to: public/fonts/manrope-OFL.txt
  - from: fonts/outfit/outfit-latin-wght-normal.woff2
    to: public/fonts/outfit-latin-wght-normal.woff2
  - from: fonts/outfit/outfit.css
    to: src/fonts/outfit.css
  - from: fonts/outfit/outfit-OFL.txt
    to: public/fonts/outfit-OFL.txt
preview: assets/preview/tpl-pricing-invoicing-desktop.jpg
---

## Pricing page

Outfit + Manrope, burnt orange on slate. For a product's plans and prices.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in
`src/sections/` and the font files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />`
(a Vite + React project with `tailwindcss` and `@tailwindcss/vite`).

Then adapt: replace every plan, price, limit and answer with the product's own; change the palette in the `@theme` block of index.css to
the DESIGN.md tokens (keep the token names); keep one filled button, on the plan you want chosen; run the audit at 1280 and 375 px and look at the
screenshots. Do not ship the example copy.
