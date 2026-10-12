---
id: pair-elegant-serif
type: font-pairing
title: Elegant serif and clean sans
summary: "Playfair Display for large headlines, DM Sans for text. Pairs with `dir-minimal-monochrome`."
moods: [elegant, luxury, calm]
products: [portfolio, fashion, hospitality, architecture]
tags: [font, typography, pairing, offline]
density: any
dependencies: []
licence: OFL-1.1
source: "bundled fonts Playfair Display and DM Sans (Fontsource, 5.3.0)"
tested: both fonts and their CSS checked by tests/test_fonts.py (D-268)
files:
  - from: fonts/playfair-display/playfair-display-latin-wght-normal.woff2
    to: public/fonts/playfair-display-latin-wght-normal.woff2
  - from: fonts/playfair-display/playfair-display.css
    to: src/fonts/playfair-display.css
  - from: fonts/playfair-display/playfair-display-OFL.txt
    to: public/fonts/playfair-display-OFL.txt
  - from: fonts/dm-sans/dm-sans-latin-wght-normal.woff2
    to: public/fonts/dm-sans-latin-wght-normal.woff2
  - from: fonts/dm-sans/dm-sans.css
    to: src/fonts/dm-sans.css
  - from: fonts/dm-sans/dm-sans-OFL.txt
    to: public/fonts/dm-sans-OFL.txt
---

## Elegant serif and clean sans

Playfair Display for large headlines, DM Sans for text. Pairs with `dir-minimal-monochrome`.

Heading font: **Playfair Display** (`font-playfair-display`). Text font: **DM Sans** (`font-dm-sans`). Playfair only at 32 px and above, weight 500 to 700; body DM Sans 16 px.

```css
@import "./fonts/playfair-display.css";
@import "./fonts/dm-sans.css";
@theme {
  --font-display: "Playfair Display Variable", ui-sans-serif, system-ui, sans-serif;
  --font-sans: "DM Sans Variable", ui-sans-serif, system-ui, sans-serif;
}
```

Use `font-display` (Tailwind class `font-display`) for headings and the default `font-sans` for the rest. Both fonts are
bundled, so nothing loads from the internet.
