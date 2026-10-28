---
id: lay-react-notebook-grid
type: section
title: "React composition: Lab notebook"
summary: "Graph paper, a handwritten headline with a highlighter mark, taped experiment cards and a dashed arrow. (React, TSX with plain CSS.)"
moods: [playful, curious, handmade]
products: [science, kids, maker spaces, workshops, tutorials]
tags: [react, tsx, plain css, composition, layout, drawn svg art]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-354 compositions, converted to React in D-398)"
tested: "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions_react.py, D-398)"
files:
  - from: recipes/compositions-react/notebook-grid/Composition.tsx
    to: src/compositions/notebook-grid/Composition.tsx
  - from: recipes/compositions-react/notebook-grid/composition.css
    to: src/compositions/notebook-grid/composition.css
  - from: recipes/compositions-react/notebook-grid/tokens.css
    to: src/compositions/notebook-grid/tokens.css
preview: assets/preview/lay-notebook-grid-desktop.jpg
---
The React version of the composition `lay-notebook-grid`: the same layout, class names and drawn art as the HTML file, as a component with its own stylesheet and a token file. Copy the three files, replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`), replace the sample words and redraw the SVG for the product, and render `<Composition />` from the app. Use it as the layout of one candidate in `design_candidates` (`composition: lay-react-notebook-grid` is also accepted); do not ship it unchanged.
