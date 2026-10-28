---
id: lay-react-menu-list
type: section
title: "React composition: Menu with leaders"
summary: "A printed-menu layout: numbered dishes, dotted leaders to the price, two columns, a ruled heading and a drawn bowl. (React, TSX with plain CSS.)"
moods: [warm, refined, dark]
products: [restaurants, cafes, bars, price lists]
tags: [react, tsx, plain css, composition, layout, drawn svg art]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-354 compositions, converted to React in D-398)"
tested: "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions_react.py, D-398)"
files:
  - from: recipes/compositions-react/menu-list/Composition.tsx
    to: src/compositions/menu-list/Composition.tsx
  - from: recipes/compositions-react/menu-list/composition.css
    to: src/compositions/menu-list/composition.css
  - from: recipes/compositions-react/menu-list/tokens.css
    to: src/compositions/menu-list/tokens.css
preview: assets/preview/lay-menu-list-desktop.jpg
---
The React version of the composition `lay-menu-list`: the same layout, class names and drawn art as the HTML file, as a component with its own stylesheet and a token file. Copy the three files, replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`), replace the sample words and redraw the SVG for the product, and render `<Composition />` from the app. Use it as the layout of one candidate in `design_candidates` (`composition: lay-react-menu-list` is also accepted); do not ship it unchanged.
