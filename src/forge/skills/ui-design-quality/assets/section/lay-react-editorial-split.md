---
id: lay-react-editorial-split
type: section
title: "React composition: Editorial split"
summary: "A large serif headline with a small-caps dateline, thin rules and a tall arch of drawn landscape art. (React, TSX with plain CSS.)"
moods: [warm, calm, editorial]
products: [care, culture, education, boutique, libraries]
tags: [react, tsx, plain css, composition, layout, drawn svg art]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-354 compositions, converted to React in D-398)"
tested: "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions_react.py, D-398)"
files:
  - from: recipes/compositions-react/editorial-split/Composition.tsx
    to: src/compositions/editorial-split/Composition.tsx
  - from: recipes/compositions-react/editorial-split/composition.css
    to: src/compositions/editorial-split/composition.css
  - from: recipes/compositions-react/editorial-split/tokens.css
    to: src/compositions/editorial-split/tokens.css
preview: assets/preview/lay-editorial-split-desktop.jpg
---
The React version of the composition `lay-editorial-split`: the same layout, class names and drawn art as the HTML file, as a component with its own stylesheet and a token file. Copy the three files, replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`), replace the sample words and redraw the SVG for the product, and render `<Composition />` from the app. Use it as the layout of one candidate in `design_candidates` (`composition: lay-react-editorial-split` is also accepted); do not ship it unchanged.
