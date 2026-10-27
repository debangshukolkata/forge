---
id: lay-react-wellness-retreat
type: section
title: "React composition: Wellness retreat"
summary: "A calm brand page: centred hero with one button over a drawn sun and hills, numbered day steps and a team grid with drawn avatars. (React, TSX with plain CSS.)"
moods: [calm, warm, natural, refined]
products: [yoga studios, wellness, spas, retreats, meditation, coaching]
tags: [react, tsx, plain css, composition, layout, drawn svg art]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (D-354 compositions, converted to React in D-398)"
tested: "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions_react.py, D-398)"
files:
  - from: recipes/compositions-react/wellness-retreat/Composition.tsx
    to: src/compositions/wellness-retreat/Composition.tsx
  - from: recipes/compositions-react/wellness-retreat/composition.css
    to: src/compositions/wellness-retreat/composition.css
  - from: recipes/compositions-react/wellness-retreat/tokens.css
    to: src/compositions/wellness-retreat/tokens.css
---
The React version of the composition `lay-wellness-retreat`: the same layout, class names and drawn art as the HTML file, as a component with its own stylesheet and a token file. Copy the three files, replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`), replace the sample words and redraw the SVG for the product, and render `<Composition />` from the app. Use it as the layout of one candidate in `design_candidates` (`composition: lay-react-wellness-retreat` is also accepted); do not ship it unchanged.
