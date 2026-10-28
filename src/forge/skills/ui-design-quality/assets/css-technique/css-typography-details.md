---
id: css-typography-details
type: css-technique
title: "Typography details"
summary: "Snippets for typography details."
moods: [typesetting]
products: [web, landing, app, dashboard]
tags: [css, html, native, no dependency]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (recipes/css-techniques.md)"
tested: snippets follow current Chromium (Edge) behaviour; checked when the recipe was written (D-251)
---

## Typography details
```css
body { font-feature-settings: "ss01", "cv11"; font-variant-numeric: tabular-nums; -webkit-font-smoothing: antialiased; }
h1, h2 { letter-spacing: -0.02em; }
.eyebrow { text-transform: uppercase; letter-spacing: .14em; font-size: .75rem; }
.drop-cap::first-letter { float: left; font: 700 4rem/1 var(--font-display); padding-right: .5rem; }
@font-face { font-family: "Inter"; src: url(/fonts/InterVariable.woff2) format("woff2"); font-display: swap; font-weight: 100 900; }
```
Offline-safe fonts: `npm i @fontsource-variable/inter @fontsource-variable/fraunces` (OFL licence) and import them in main.tsx, so the page
looks right even with no internet.
