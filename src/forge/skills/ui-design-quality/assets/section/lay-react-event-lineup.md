---
id: lay-react-event-lineup
type: section
title: "React composition: Event lineup"
summary: "A one-day festival page: poster hero with a drawn stage and crowd, time-column schedule with tracks, artist cards, three ticket tiers and a venue card. (React, TSX with plain CSS.)"
moods: [bold, dark, energetic]
products: [festivals, conferences, concerts, club nights, meetups]
tags: [react, tsx, plain css, composition, layout, drawn svg art]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-354 compositions, converted to React in D-398)"
tested: "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions_react.py, D-398)"
files:
  - from: recipes/compositions-react/event-lineup/Composition.tsx
    to: src/compositions/event-lineup/Composition.tsx
  - from: recipes/compositions-react/event-lineup/composition.css
    to: src/compositions/event-lineup/composition.css
  - from: recipes/compositions-react/event-lineup/tokens.css
    to: src/compositions/event-lineup/tokens.css
preview: assets/preview/lay-event-lineup-desktop.jpg
---
The React version of the composition `lay-event-lineup`: the same layout, class names and drawn art as the HTML file, as a component with its own stylesheet and a token file. Copy the three files, replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`), replace the sample words and redraw the SVG for the product, and render `<Composition />` from the app. Use it as the layout of one candidate in `design_candidates` (`composition: lay-react-event-lineup` is also accepted); do not ship it unchanged.
