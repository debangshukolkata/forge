---
id: dir-bento
type: direction
title: Bento and cards
summary: "An unequal grid of rounded tiles, each holding one idea: a number, a chart, a quote."
moods: [modern, organised, friendly]
products: [feature overviews, personal sites, dashboards]
tags: [visual direction, any clean sans]
density: balanced
dependencies: []
licence: original
source: authored for DebCraft (style-directions.md, D-251)
preview: assets/preview/ds-bento-specimen.jpg
tested: "text direction used in the three-design task (D-251, D-252); not yet rendered as its own preview"
---

## Bento and cards

Layout built from an unequal grid of rounded tiles (2x2, 1x2, 1x1) each holding one idea: a number, a chart, a quote,
a mini illustration. Palette: neutral tiles with two tinted accents. Use CSS grid with `grid-template-areas` or
`col-span-2 row-span-2`. Works for: feature overviews, personal sites, dashboards' home.
```css
.bento { display: grid; gap: 1rem; grid-template-columns: repeat(4, 1fr); grid-auto-rows: 12rem; }
.bento > :nth-child(1) { grid-column: span 2; grid-row: span 2; }
@media (max-width: 767px) { .bento { grid-template-columns: 1fr; grid-auto-rows: auto; } .bento > * { grid-column: auto !important; grid-row: auto !important; } }
```
