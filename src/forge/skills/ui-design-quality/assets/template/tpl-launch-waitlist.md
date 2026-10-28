---
id: tpl-launch-waitlist
type: template
title: "Landing page: product launch or waiting list"
summary: "One e-mail field in the first view, then press logos, tabbed how-it-works, a before and after, a plan table, questions and a newsletter band."
moods: [focused, modern, crisp]
products: [app, saas, waiting list, launch, startup, software]
tags: [react, tailwind v4, page, landing, sign-up, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-514); fonts from Fontsource, see the OFL texts copied with them"
tested: "NOT RUN YET (written 2026-10-28 without building; the gallery and template tests in tests/test_sections.py must pass before this is relied on)"
files:
  - from: recipes/templates/launch/App.tsx
    to: src/App.tsx
  - from: recipes/templates/launch/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/HeroSignup.tsx
    to: src/sections/HeroSignup.tsx
  - from: recipes/sections/LogoStrip.tsx
    to: src/sections/LogoStrip.tsx
  - from: recipes/sections/FeaturesTabs.tsx
    to: src/sections/FeaturesTabs.tsx
  - from: recipes/sections/FeaturesComparison.tsx
    to: src/sections/FeaturesComparison.tsx
  - from: recipes/sections/PricingTable.tsx
    to: src/sections/PricingTable.tsx
  - from: recipes/sections/FaqList.tsx
    to: src/sections/FaqList.tsx
  - from: recipes/sections/NewsletterBand.tsx
    to: src/sections/NewsletterBand.tsx
  - from: recipes/sections/FooterMinimal.tsx
    to: src/sections/FooterMinimal.tsx
  - from: fonts/space-grotesk/space-grotesk-latin-wght-normal.woff2
    to: public/fonts/space-grotesk-latin-wght-normal.woff2
  - from: fonts/space-grotesk/space-grotesk.css
    to: src/fonts/space-grotesk.css
  - from: fonts/space-grotesk/space-grotesk-OFL.txt
    to: public/fonts/space-grotesk-OFL.txt
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
---

## Landing page: product launch or waiting list

Space Grotesk + Inter, indigo on neutral grey. Pairs with direction `dir-clean-product` and palette `pal-modern-product`.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in
`src/sections/`, and the font files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />`
(a Vite + React project; `npm create vite@latest` with the React TypeScript template and `npm i tailwindcss @tailwindcss/vite`, plugin in vite.config).

Then adapt: replace every claim, plan, price and answer with the real product's, and send the e-mail from `HeroSignup`'s `onSubmit` to the real list
(it only validates on the page). Do not claim press coverage or customers the product does not have: remove `LogoStrip` until it does. Change the palette in
the `@theme` block of index.css to the DESIGN.md tokens (keep the token names); run the audit at 1280 and 375 px and look at the screenshots.
