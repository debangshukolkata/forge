---
id: tpl-form-flow
type: template
title: "Form flow: booking, application or registration"
summary: "A short page whose one job is a three-step form with progress and review, then what happens next and a few answers."
moods: [calm, guided, clear]
products: [booking, application, registration, onboarding, sign-up form]
tags: [react, tailwind v4, page, form, wizard, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-514); uses the clinic palette and fonts; fonts from Fontsource, see the OFL texts copied with them"
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-514, D-515)"
files:
  - from: recipes/templates/formflow/App.tsx
    to: src/App.tsx
  - from: recipes/templates/clinic/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/FormStepper.tsx
    to: src/sections/FormStepper.tsx
  - from: recipes/sections/FeaturesIconRow.tsx
    to: src/sections/FeaturesIconRow.tsx
  - from: recipes/sections/FaqList.tsx
    to: src/sections/FaqList.tsx
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
preview: assets/preview/tpl-form-flow-desktop.jpg
---

## Form flow: booking, application or registration

Plus Jakarta Sans + Manrope, teal on cool grey (the palette of `tpl-landing-clinic`).

Copies a complete page into the project: `src/App.tsx`, `src/index.css`, the sections and the font files with their licence texts. `src/main.tsx` should
import `./index.css` and render `<App />` (a Vite + React project with Tailwind v4).

Then adapt: change the `steps` and their `fields` in `FormStepper` to what the process really needs (ask for as little as possible), send the values from
`onSubmit` to the real back end (the page only validates), and replace every sentence. Run the audit at 1280 and 375 px and look at the screenshots.
