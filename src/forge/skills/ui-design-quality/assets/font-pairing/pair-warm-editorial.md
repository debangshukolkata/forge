---
id: pair-warm-editorial
type: font-pairing
title: Warm editorial
summary: "Fraunces for headlines, Inter for text. Pairs with direction `dir-soft-editorial`."
moods: [warm, editorial, trustworthy]
products: [charity, health, education, boutique]
tags: [font, typography, pairing, offline]
density: any
dependencies: []
licence: OFL-1.1
source: "bundled fonts Fraunces and Inter (Fontsource, 5.3.0)"
preview: assets/preview/pair-warm-editorial.jpg
tested: both fonts and their CSS checked by tests/test_fonts.py (D-268)
files:
  - from: fonts/fraunces/fraunces-latin-wght-normal.woff2
    to: public/fonts/fraunces-latin-wght-normal.woff2
  - from: fonts/fraunces/fraunces.css
    to: src/fonts/fraunces.css
  - from: fonts/fraunces/fraunces-OFL.txt
    to: public/fonts/fraunces-OFL.txt
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
---

## Warm editorial

Fraunces for headlines, Inter for text. Pairs with direction `dir-soft-editorial`.

Heading font: **Fraunces** (`font-fraunces`). Text font: **Inter** (`font-inter`). Headlines 36 to 64 px, weight 600, tracking -0.01em; body 16 to 18 px Inter, line-height 1.6.

```css
@import "./fonts/fraunces.css";
@import "./fonts/inter.css";
@theme {
  --font-display: "Fraunces Variable", ui-sans-serif, system-ui, sans-serif;
  --font-sans: "Inter Variable", ui-sans-serif, system-ui, sans-serif;
}
```

Use `font-display` (Tailwind class `font-display`) for headings and the default `font-sans` for the rest. Both fonts are
bundled, so nothing loads from the internet.
