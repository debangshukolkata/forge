---
id: pair-heavy-grotesque
type: font-pairing
title: Heavy grotesque
summary: "Archivo at heavy weights for headlines, Inter for text."
moods: [bold, strong, sporty]
products: [sport, news, campaigns]
tags: [font, typography, pairing, offline]
density: any
dependencies: []
licence: OFL-1.1
source: "bundled fonts Archivo and Inter (Fontsource, 5.3.0)"
tested: both fonts and their CSS checked by tests/test_fonts.py (D-268)
files:
  - from: fonts/archivo/archivo-latin-wght-normal.woff2
    to: public/fonts/archivo-latin-wght-normal.woff2
  - from: fonts/archivo/archivo.css
    to: src/fonts/archivo.css
  - from: fonts/archivo/archivo-OFL.txt
    to: public/fonts/archivo-OFL.txt
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
---

## Heavy grotesque

Archivo at heavy weights for headlines, Inter for text.

Heading font: **Archivo** (`font-archivo`). Text font: **Inter** (`font-inter`). Headlines weight 800 to 900; keep body Inter 16 px; strong colour blocks.

```css
@import "./fonts/archivo.css";
@import "./fonts/inter.css";
@theme {
  --font-display: "Archivo Variable", ui-sans-serif, system-ui, sans-serif;
  --font-sans: "Inter Variable", ui-sans-serif, system-ui, sans-serif;
}
```

Use `font-display` (Tailwind class `font-display`) for headings and the default `font-sans` for the rest. Both fonts are
bundled, so nothing loads from the internet.
