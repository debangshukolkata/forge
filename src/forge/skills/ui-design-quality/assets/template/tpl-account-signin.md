---
id: tpl-account-signin
type: template
title: "Sign-in page"
summary: "Only a sign-in form and a quiet footer: e-mail, password with show and hide, remember me and a forgotten-password link."
moods: [plain, focused, trustworthy]
products: [login, sign in, account, members area, portal, app]
tags: [react, tailwind v4, page, login, form, offline fonts]
density: airy
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-514); uses the launch palette and fonts; fonts from Fontsource, see the OFL texts copied with them"
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-514, D-515)"
files:
  - from: recipes/templates/signin/App.tsx
    to: src/App.tsx
  - from: recipes/templates/launch/index.css
    to: src/index.css
  - from: recipes/sections/FormLogin.tsx
    to: src/sections/FormLogin.tsx
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
preview: assets/preview/tpl-account-signin-desktop.jpg
---

## Sign-in page

Space Grotesk + Inter, indigo on neutral grey (the palette of `tpl-launch-waitlist`).

Copies a complete page into the project: `src/App.tsx`, `src/index.css`, the sections and the font files with their licence texts. `src/main.tsx` should
import `./index.css` and render `<App />` (a Vite + React project with Tailwind v4).

Then adapt: wire `FormLogin`'s `onSubmit` to the real sign-in and return the refusal text to show; point the forgotten-password and create-account links at
the real pages; replace the product name. Never keep the password in the page state longer than the submit. Run the audit at 1280 and 375 px and look at
the screenshots.
