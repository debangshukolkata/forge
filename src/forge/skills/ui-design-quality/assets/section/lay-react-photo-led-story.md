---
id: lay-react-photo-led-story
type: section
title: "React composition: Photo-led story page"
summary: "A page told in bands: a hero photograph to the page edge with the headline on its fade, a ruled facts strip with line icons, three product photographs, a dark band beside a photograph, a light band beside the shop front. (React, TSX with plain CSS.)"
moods: [warm, appetising, editorial, calm]
products: [bakery, restaurant, cafe, shop, studio, hotel, farm]
tags: [react, tsx, plain css, composition, layout, drawn svg art]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-354 compositions, converted to React in D-398)"
tested: "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions_react.py, D-398)"
files:
  - from: recipes/compositions-react/photo-led-story/Composition.tsx
    to: src/compositions/photo-led-story/Composition.tsx
  - from: recipes/compositions-react/photo-led-story/composition.css
    to: src/compositions/photo-led-story/composition.css
  - from: recipes/compositions-react/photo-led-story/tokens.css
    to: src/compositions/photo-led-story/tokens.css
preview: assets/preview/lay-photo-led-story-desktop.jpg
---
The React version of the composition `lay-photo-led-story`: the same layout, class names and drawn art as the HTML file, as a component with its own stylesheet and a token file. Copy the three files, replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`), replace the sample words and redraw the SVG for the product, and render `<Composition />` from the app. Use it as the layout of one candidate in `design_candidates` (`composition: lay-react-photo-led-story` is also accepted); do not ship it unchanged.
