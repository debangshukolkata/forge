---
id: tpl-docs-product
type: template
title: "Docs: product documentation"
summary: "A documentation page: top bar, sticky navigation, article with a code block and a note, an On this page list, footer."
moods: [technical, calm, clear]
products: [documentation, developer tools, api, help centre]
tags: [react, tailwind v4, page, offline fonts]
density: balanced
dependencies: []
licence: "original (fonts: OFL-1.1)"
source: "authored for DebCraft (templates, D-385); fonts from Fontsource, see the OFL texts copied with them"
tested: "built with Vite + Tailwind v4, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-385)"
files:
  - from: recipes/templates/docs/App.tsx
    to: src/App.tsx
  - from: recipes/templates/docs/index.css
    to: src/index.css
  - from: recipes/sections/NavBar.tsx
    to: src/sections/NavBar.tsx
  - from: recipes/sections/DocsShell.tsx
    to: src/sections/DocsShell.tsx
  - from: recipes/sections/FooterColumns.tsx
    to: src/sections/FooterColumns.tsx
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
  - from: fonts/jetbrains-mono/jetbrains-mono-latin-wght-normal.woff2
    to: public/fonts/jetbrains-mono-latin-wght-normal.woff2
  - from: fonts/jetbrains-mono/jetbrains-mono.css
    to: src/fonts/jetbrains-mono.css
  - from: fonts/jetbrains-mono/jetbrains-mono-OFL.txt
    to: public/fonts/jetbrains-mono-OFL.txt
preview: assets/preview/tpl-docs-product-desktop.jpg
---

## Docs: product documentation

Inter + JetBrains Mono, teal on slate. For API and product documentation.

Copies a complete page into the project: `src/App.tsx` (the composition), `src/index.css` (tokens and fonts), the sections it uses in
`src/sections/`, and the font files in `public/fonts/` with their licence texts. `src/main.tsx` should import `./index.css` and render `<App />`
(a Vite + React project; `npm create vite@latest` with the React TypeScript template and `npm i tailwindcss @tailwindcss/vite`, plugin in vite.config).

Then adapt: replace every example text, number and link with the product's own; change the palette in the `@theme` block of index.css to
the DESIGN.md tokens (keep the token names); remove sections the product does not need; run the audit at 1280 and 375 px and look at the
screenshots. Do not ship the example copy.
