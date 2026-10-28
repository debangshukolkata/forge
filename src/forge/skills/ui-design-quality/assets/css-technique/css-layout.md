---
id: css-layout
type: css-technique
title: "Layout"
summary: "Snippets for layout."
moods: [responsive]
products: [stylesheet]
tags: [css, technique]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (recipes/css-techniques.md)"
tested: snippets follow current Chromium (Edge) behaviour; checked when the recipe was written (D-251)
---

## Layout
```css
/* fluid type and spacing without media queries */
h1 { font-size: clamp(2.25rem, 1.2rem + 4vw, 4.5rem); line-height: 1.05; text-wrap: balance; }
p  { text-wrap: pretty; max-width: 65ch; }
section { padding-block: clamp(4rem, 8vw, 7rem); }

/* auto-fit grid: as many 16rem columns as fit, no breakpoints */
.grid-auto { display: grid; gap: 1.5rem; grid-template-columns: repeat(auto-fit, minmax(min(16rem, 100%), 1fr)); }

/* container queries: a component adapts to the space it is given, not the window */
.card-wrap { container-type: inline-size; }
@container (min-width: 28rem) { .card { display: grid; grid-template-columns: 8rem 1fr; gap: 1rem; } }

/* subgrid: align inner rows across sibling cards (titles, text, buttons line up) */
.cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; }
.cards > .card { display: grid; grid-row: span 3; grid-template-rows: subgrid; }

/* full height that respects mobile browser bars */
.hero { min-height: 100dvh; }

/* sticky sidebar / header */
.sticky-col { position: sticky; top: 6rem; align-self: start; }

/* aspect ratio and object fit for any image/video/map */
.media { aspect-ratio: 4 / 3; object-fit: cover; width: 100%; border-radius: 1rem; }
```
