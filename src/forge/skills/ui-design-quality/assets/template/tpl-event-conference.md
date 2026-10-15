---
id: tpl-event-conference
type: template
title: "Event: conference"
summary: "A conference or festival page: hero, key numbers, a programme with day tabs, speakers, tickets, practical questions, closing band."
moods: [bold, organised, modern]
products: [events, conferences, festivals, meetups]
tags: [react, tailwind v4, page, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-385); fonts from Fontsource, see the OFL texts copied with them"
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-385)"
files:
  - from: recipes/templates/event/App.tsx
    to: src/App.tsx
  - from: recipes/templates/event/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/HeroCentered.tsx
    to: src/sections/HeroCentered.tsx
  - from: recipes/sections/StatsRow.tsx
    to: src/sections/StatsRow.tsx
  - from: recipes/sections/ScheduleList.tsx
    to: src/sections/ScheduleList.tsx
  - from: recipes/sections/SpeakerGrid.tsx
    to: src/sections/SpeakerGrid.tsx
  - from: recipes/sections/PricingTiers.tsx
    to: src/sections/PricingTiers.tsx
  - from: recipes/sections/FaqList.tsx
    to: src/sections/FaqList.tsx
  - from: recipes/sections/CtaBand.tsx
    to: src/sections/CtaBand.tsx
  - from: recipes/sections/FooterColumns.tsx
    to: src/sections/FooterColumns.tsx
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

## Event: conference

Space Grotesk + Inter, a bold orange on cool slate with tighter corners. For conferences, festivals and meetups.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in
`src/sections/`, and the font files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />`
(a Vite + React project; `npm create vite@latest` with the React TypeScript template and `npm i tailwindcss @tailwindcss/vite`, plugin in vite.config).

Then adapt: replace every example text, number and link with the product's own; change the palette in the `@theme` block of index.css to
the DESIGN.md tokens (keep the token names); remove sections the product does not need; run the audit at 1280 and 375 px and look at the
screenshots. Do not ship the example copy.
