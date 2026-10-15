---
id: sec-features-ruled
type: section
title: Ruled feature list
summary: "A ruled list instead of a row of cards: a large numeral, a title, a sentence and a small label on each row between hairlines."
moods: [editorial, calm, precise]
products: [course, programme, service, agency, principles]
tags: [react, tailwind v4, tokens only, features, card-free]
density: balanced
dependencies: []
licence: original
source: "authored for DebCraft (section library, D-432)"
preview: assets/preview/sec-features-ruled.jpg
tested: "built with Vite + Tailwind v4 with the three template palettes, type-checked (tsc strict), audit clean at 1280 and 375 px, screenshots looked at (tests/test_sections.py, D-432)"
files:
  - from: recipes/sections/FeaturesRuled.tsx
    to: src/sections/FeaturesRuled.tsx
---

## Ruled feature list

Component `FeaturesRuled` in `src/sections/FeaturesRuled.tsx`. Every prop has a default (example content): pass your own `items` (title, text, optional label and
optional `href`; a row with `href` is a link as a whole). It uses only the theme token classes of `index.css`, so changing the tokens restyles it. Needs the
`index.css` token file (asset `tpl-landing-charity`, `tpl-landing-saas` or `tpl-landing-portfolio` ships one, or copy `recipes/index.css`).

Rules: three to six rows; replace the example copy completely (the audit flags placeholder text); use it where a row of identical cards would be the machine-made
choice (what a service includes, the programme of a course, the principles of a brand). Boxes are for objects; this list is for statements.
