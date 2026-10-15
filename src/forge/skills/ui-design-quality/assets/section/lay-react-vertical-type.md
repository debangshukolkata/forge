---
id: lay-react-vertical-type
type: section
title: "React composition: Vertical type"
summary: "An oversized vertical word like a shop sign beside a quiet text block and a drawn paper lantern; set for Japanese or East Asian type. (React, TSX with plain CSS.)"
moods: [dramatic, night, craft]
products: [late-night food, japanese brands, bars, craft]
tags: [react, tsx, plain css, composition, layout, drawn svg art]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-354 compositions, converted to React in D-398)"
tested: "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions_react.py, D-398)"
files:
  - from: recipes/compositions-react/vertical-type/Composition.tsx
    to: src/compositions/vertical-type/Composition.tsx
  - from: recipes/compositions-react/vertical-type/composition.css
    to: src/compositions/vertical-type/composition.css
  - from: recipes/compositions-react/vertical-type/tokens.css
    to: src/compositions/vertical-type/tokens.css
---
The React version of the composition `lay-vertical-type`: the same layout, class names and drawn art as the HTML file, as a component with its own stylesheet and a token file. Copy the three files, replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`), replace the sample words and redraw the SVG for the product, and render `<Composition />` from the app. Use it as the layout of one candidate in `design_candidates` (`composition: lay-react-vertical-type` is also accepted); do not ship it unchanged.
