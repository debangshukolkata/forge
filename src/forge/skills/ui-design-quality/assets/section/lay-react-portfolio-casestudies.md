---
id: lay-react-portfolio-casestudies
type: section
title: "React composition: Portfolio case studies"
summary: "A monochrome editorial portfolio: masonry grid of drawn work tiles, case-study cards with a one-line result, an about strip and a contact line. (React, TSX with plain CSS.)"
moods: [editorial, minimal, refined]
products: [designer portfolios, photographer portfolios, studios, freelancers, agencies]
tags: [react, tsx, plain css, composition, layout, drawn svg art]
density: airy
dependencies: []
licence: original
source: "authored for DebCraft (D-354 compositions, converted to React in D-398)"
tested: "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions_react.py, D-398)"
files:
  - from: recipes/compositions-react/portfolio-casestudies/Composition.tsx
    to: src/compositions/portfolio-casestudies/Composition.tsx
  - from: recipes/compositions-react/portfolio-casestudies/composition.css
    to: src/compositions/portfolio-casestudies/composition.css
  - from: recipes/compositions-react/portfolio-casestudies/tokens.css
    to: src/compositions/portfolio-casestudies/tokens.css
preview: assets/preview/lay-portfolio-casestudies-desktop.jpg
---
The React version of the composition `lay-portfolio-casestudies`: the same layout, class names and drawn art as the HTML file, as a component with its own stylesheet and a token file. Copy the three files, replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`), replace the sample words and redraw the SVG for the product, and render `<Composition />` from the app. Use it as the layout of one candidate in `design_candidates` (`composition: lay-react-portfolio-casestudies` is also accepted); do not ship it unchanged.
