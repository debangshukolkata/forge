---
id: lay-react-school-courses
type: section
title: "React composition: Lantern Academy courses"
summary: "A friendly academy page: split hero with a drawn open book, course list with date, length and price, numbered enrolment steps, teachers and three testimonial cards. (React, TSX with plain CSS.)"
moods: [friendly, bright, playful]
products: [schools, online academies, tutoring, workshops, training providers]
tags: [react, tsx, plain css, composition, layout, drawn svg art]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (D-354 compositions, converted to React in D-398)"
tested: "built with Vite and React (type-checked), rendered in Edge at 1280 and 375 px: no sideways scroll, the style audit reports nothing (tests/test_compositions_react.py, D-398)"
files:
  - from: recipes/compositions-react/school-courses/Composition.tsx
    to: src/compositions/school-courses/Composition.tsx
  - from: recipes/compositions-react/school-courses/composition.css
    to: src/compositions/school-courses/composition.css
  - from: recipes/compositions-react/school-courses/tokens.css
    to: src/compositions/school-courses/tokens.css
---
The React version of the composition `lay-school-courses`: the same layout, class names and drawn art as the HTML file, as a component with its own stylesheet and a token file. Copy the three files, replace `tokens.css` with the tokens exported from DESIGN.md (`design_md_export css-variables`), replace the sample words and redraw the SVG for the product, and render `<Composition />` from the app. Use it as the layout of one candidate in `design_candidates` (`composition: lay-react-school-courses` is also accepted); do not ship it unchanged.
