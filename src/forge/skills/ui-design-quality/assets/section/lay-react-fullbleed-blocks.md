---
id: lay-react-fullbleed-blocks
type: section
title: "React composition: Full-bleed colour blocks"
summary: "Sections as edge-to-edge colour bands with huge numbers and off-centre text, so the page has rhythm. (React, TSX with plain CSS.)"
moods: [confident, modern, bold]
products: [studios, agencies, product stories, reports]
tags: [react, tsx, plain css, composition, layout, drawn svg art]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-354 compositions, converted to React in D-398)"
tested: "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions_react.py, D-398)"
files:
  - from: recipes/compositions-react/fullbleed-blocks/Composition.tsx
    to: src/compositions/fullbleed-blocks/Composition.tsx
  - from: recipes/compositions-react/fullbleed-blocks/composition.css
    to: src/compositions/fullbleed-blocks/composition.css
  - from: recipes/compositions-react/fullbleed-blocks/tokens.css
    to: src/compositions/fullbleed-blocks/tokens.css
preview: assets/preview/lay-fullbleed-blocks-desktop.jpg
---
The React version of the composition `lay-fullbleed-blocks`: the same layout, class names and drawn art as the HTML file, as a component with its own stylesheet and a token file. Copy the three files, replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`), replace the sample words and redraw the SVG for the product, and render `<Composition />` from the app. Use it as the layout of one candidate in `design_candidates` (`composition: lay-react-fullbleed-blocks` is also accepted); do not ship it unchanged.
