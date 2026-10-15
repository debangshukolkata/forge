---
id: pair-fintech-precise
type: font-pairing
title: Precise fintech
summary: "Manrope for headings and numbers, Inter for text."
moods: [precise, technical, trustworthy]
products: [fintech, dashboards, b2b]
tags: [font, typography, pairing, offline]
density: any
dependencies: []
licence: OFL-1.1
source: "bundled fonts Manrope and Inter (Fontsource, 5.3.0)"
preview: assets/preview/pair-fintech-precise.jpg
tested: both fonts and their CSS checked by tests/test_fonts.py (D-268)
files:
  - from: fonts/manrope/manrope-latin-wght-normal.woff2
    to: public/fonts/manrope-latin-wght-normal.woff2
  - from: fonts/manrope/manrope.css
    to: src/fonts/manrope.css
  - from: fonts/manrope/manrope-OFL.txt
    to: public/fonts/manrope-OFL.txt
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
---

## Precise fintech

Manrope for headings and numbers, Inter for text.

Heading font: **Manrope** (`font-manrope`). Text font: **Inter** (`font-inter`). Use tabular figures (`font-variant-numeric: tabular-nums`) for amounts.

```css
@import "./fonts/manrope.css";
@import "./fonts/inter.css";
@theme {
  --font-display: "Manrope Variable", ui-sans-serif, system-ui, sans-serif;
  --font-sans: "Inter Variable", ui-sans-serif, system-ui, sans-serif;
}
```

Use `font-display` (Tailwind class `font-display`) for headings and the default `font-sans` for the rest. Both fonts are
bundled, so nothing loads from the internet.
