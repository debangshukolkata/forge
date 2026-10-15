---
id: pair-bold-poster
type: font-pairing
title: Bold poster
summary: "Space Grotesk huge and tight, Inter for small text. Pairs with `dir-bold-poster`."
moods: [bold, loud, techy]
products: [events, campaigns, launches, developer tools]
tags: [font, typography, pairing, offline]
density: any
dependencies: []
licence: OFL-1.1
source: "bundled fonts Space Grotesk and Inter (Fontsource, 5.3.0)"
preview: assets/preview/pair-bold-poster.jpg
tested: both fonts and their CSS checked by tests/test_fonts.py (D-268)
files:
  - from: fonts/space-grotesk/space-grotesk-latin-wght-normal.woff2
    to: public/fonts/space-grotesk-latin-wght-normal.woff2
  - from: fonts/space-grotesk/space-grotesk.css
    to: src/fonts/space-grotesk.css
  - from: fonts/space-grotesk/space-grotesk-OFL.txt
    to: public/fonts/space-grotesk-OFL.txt
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
---

## Bold poster

Space Grotesk huge and tight, Inter for small text. Pairs with `dir-bold-poster`.

Heading font: **Space Grotesk** (`font-space-grotesk`). Text font: **Inter** (`font-inter`). Headlines 72 to 140 px, weight 700, tracking -0.04em, uppercase labels in 12 px Inter with 0.1em tracking.

```css
@import "./fonts/space-grotesk.css";
@import "./fonts/inter.css";
@theme {
  --font-display: "Space Grotesk Variable", ui-sans-serif, system-ui, sans-serif;
  --font-sans: "Inter Variable", ui-sans-serif, system-ui, sans-serif;
}
```

Use `font-display` (Tailwind class `font-display`) for headings and the default `font-sans` for the rest. Both fonts are
bundled, so nothing loads from the internet.
