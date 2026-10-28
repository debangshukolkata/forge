---
id: tpl-landing-newsletter
type: template
title: "Landing page: newsletter or publication sign-up"
summary: "Indigo page: one e-mail field first, what you get each week, what readers say and a second sign-up at the bottom."
moods: [focused, plain, modern]
products: [newsletter, publication, blog, podcast, substack, mailing list]
tags: [react, tailwind v4, page, landing, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-515); fonts from Fontsource, see the OFL texts copied with them"
tested: "NOT RUN YET (written 2026-10-28 without building; the gallery and template tests in tests/test_sections.py must pass before this is relied on)"
files:
  - from: recipes/templates/newsletter/App.tsx
    to: src/App.tsx
  - from: recipes/templates/launch/index.css
    to: src/index.css
  - from: recipes/sections/HeroSignup.tsx
    to: src/sections/HeroSignup.tsx
  - from: recipes/sections/FeaturesNumbered.tsx
    to: src/sections/FeaturesNumbered.tsx
  - from: recipes/sections/TestimonialColumns.tsx
    to: src/sections/TestimonialColumns.tsx
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

## Landing page: newsletter or publication sign-up

Space Grotesk + Inter, indigo on neutral grey (the palette of `tpl-launch-waitlist`). Say honestly how often it is sent and connect both forms to the real mailing list.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in `src/sections/`, and the font
files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />` (a Vite + React project with Tailwind v4).

Then adapt: replace every example name, figure and sentence with the product's own, change the palette in the `@theme` block of index.css to the DESIGN.md tokens
(keep the token names), run the audit at 1280 and 375 px and look at the screenshots. Do not ship the example copy.
