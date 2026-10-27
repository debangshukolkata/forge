---
id: lay-react-saas-product-tour
type: section
title: "React composition: Plumbline product tour"
summary: "A B2B software page: centred hero with a drawn app window, alternating feature rows, a plan comparison table, two-column FAQ and a logo wall. (React, TSX with plain CSS.)"
moods: [clean, modern, trustworthy, cool]
products: [saas, b2b software, developer tools, internal platforms]
tags: [react, tsx, plain css, composition, layout, drawn svg art]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-354 compositions, converted to React in D-398)"
tested: "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions_react.py, D-398)"
files:
  - from: recipes/compositions-react/saas-product-tour/Composition.tsx
    to: src/compositions/saas-product-tour/Composition.tsx
  - from: recipes/compositions-react/saas-product-tour/composition.css
    to: src/compositions/saas-product-tour/composition.css
  - from: recipes/compositions-react/saas-product-tour/tokens.css
    to: src/compositions/saas-product-tour/tokens.css
---
The React version of the composition `lay-saas-product-tour`: the same layout, class names and drawn art as the HTML file, as a component with its own stylesheet and a token file. Copy the three files, replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`), replace the sample words and redraw the SVG for the product, and render `<Composition />` from the app. Use it as the layout of one candidate in `design_candidates` (`composition: lay-react-saas-product-tour` is also accepted); do not ship it unchanged.
