---
id: pair-geometric-modern
type: font-pairing
title: Geometric modern
summary: "Outfit for headings, Inter for text."
moods: [geometric, modern, playful]
products: [landing, apps, brands]
tags: [font, typography, pairing, offline]
density: any
dependencies: []
licence: OFL-1.1
source: "bundled fonts Outfit and Inter (Fontsource, 5.3.0)"
preview: assets/preview/pair-geometric-modern.jpg
tested: both fonts and their CSS checked by tests/test_fonts.py (D-268)
files:
  - from: fonts/outfit/outfit-latin-wght-normal.woff2
    to: public/fonts/outfit-latin-wght-normal.woff2
  - from: fonts/outfit/outfit.css
    to: src/fonts/outfit.css
  - from: fonts/outfit/outfit-OFL.txt
    to: public/fonts/outfit-OFL.txt
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
---

## Geometric modern

Outfit for headings, Inter for text.

Heading font: **Outfit** (`font-outfit`). Text font: **Inter** (`font-inter`). Outfit weight 600 to 800 for headings; avoid it below 20 px.

```css
@import "./fonts/outfit.css";
@import "./fonts/inter.css";
@theme {
  --font-display: "Outfit Variable", ui-sans-serif, system-ui, sans-serif;
  --font-sans: "Inter Variable", ui-sans-serif, system-ui, sans-serif;
}
```

Use `font-display` (Tailwind class `font-display`) for headings and the default `font-sans` for the rest. Both fonts are
bundled, so nothing loads from the internet.
