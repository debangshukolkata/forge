---
id: lay-react-poster-hero
type: section
title: "React composition: Poster hero"
summary: "A headline that fills the width in heavy uppercase type, a hard-shadow action, a rotated sticker, a marquee strip and a drawn sun. (React, TSX with plain CSS.)"
moods: [bold, urgent, loud]
products: [events, nightlife, launches, sport]
tags: [react, tsx, plain css, composition, layout, drawn svg art]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-354 compositions, converted to React in D-398)"
tested: "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions_react.py, D-398)"
files:
  - from: recipes/compositions-react/poster-hero/Composition.tsx
    to: src/compositions/poster-hero/Composition.tsx
  - from: recipes/compositions-react/poster-hero/composition.css
    to: src/compositions/poster-hero/composition.css
  - from: recipes/compositions-react/poster-hero/tokens.css
    to: src/compositions/poster-hero/tokens.css
---
The React version of the composition `lay-poster-hero`: the same layout, class names and drawn art as the HTML file, as a component with its own stylesheet and a token file. Copy the three files, replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`), replace the sample words and redraw the SVG for the product, and render `<Composition />` from the app. Use it as the layout of one candidate in `design_candidates` (`composition: lay-react-poster-hero` is also accepted); do not ship it unchanged.
