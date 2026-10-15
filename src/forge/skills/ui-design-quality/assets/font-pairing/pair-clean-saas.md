---
id: pair-clean-saas
type: font-pairing
title: Clean product
summary: "Plus Jakarta Sans for headings, Inter for text. Pairs with `dir-clean-product`."
moods: [clean, modern, polished]
products: [saas, startups, landing]
tags: [font, typography, pairing, offline]
density: any
dependencies: []
licence: OFL-1.1
source: "bundled fonts Plus Jakarta Sans and Inter (Fontsource, 5.3.0)"
preview: assets/preview/pair-clean-saas.jpg
tested: both fonts and their CSS checked by tests/test_fonts.py (D-268)
files:
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans-latin-wght-normal.woff2
    to: public/fonts/plus-jakarta-sans-latin-wght-normal.woff2
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans.css
    to: src/fonts/plus-jakarta-sans.css
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans-OFL.txt
    to: public/fonts/plus-jakarta-sans-OFL.txt
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
---

## Clean product

Plus Jakarta Sans for headings, Inter for text. Pairs with `dir-clean-product`.

Heading font: **Plus Jakarta Sans** (`font-plus-jakarta-sans`). Text font: **Inter** (`font-inter`). Headings weight 700, tracking -0.02em at large sizes; body Inter 16 px.

```css
@import "./fonts/plus-jakarta-sans.css";
@import "./fonts/inter.css";
@theme {
  --font-display: "Plus Jakarta Sans Variable", ui-sans-serif, system-ui, sans-serif;
  --font-sans: "Inter Variable", ui-sans-serif, system-ui, sans-serif;
}
```

Use `font-display` (Tailwind class `font-display`) for headings and the default `font-sans` for the rest. Both fonts are
bundled, so nothing loads from the internet.
