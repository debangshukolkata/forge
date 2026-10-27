---
id: lay-react-boutique-hotel
type: section
title: "React composition: Hotel Marea"
summary: "A hospitality page: full-bleed dusk hero with a drawn building and sea, a booking bar, alternating room rows, text amenities, one large guest quote and address cards. (React, TSX with plain CSS.)"
moods: [refined, calm, elegant]
products: [hotels, guesthouses, resorts, retreats, hospitality]
tags: [react, tsx, plain css, composition, layout, drawn svg art]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (D-354 compositions, converted to React in D-398)"
tested: "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions_react.py, D-398)"
files:
  - from: recipes/compositions-react/boutique-hotel/Composition.tsx
    to: src/compositions/boutique-hotel/Composition.tsx
  - from: recipes/compositions-react/boutique-hotel/composition.css
    to: src/compositions/boutique-hotel/composition.css
  - from: recipes/compositions-react/boutique-hotel/tokens.css
    to: src/compositions/boutique-hotel/tokens.css
---
The React version of the composition `lay-boutique-hotel`: the same layout, class names and drawn art as the HTML file, as a component with its own stylesheet and a token file. Copy the three files, replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`), replace the sample words and redraw the SVG for the product, and render `<Composition />` from the app. Use it as the layout of one candidate in `design_candidates` (`composition: lay-react-boutique-hotel` is also accepted); do not ship it unchanged.
