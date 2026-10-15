---
id: pair-hindi
type: font-pairing
title: Hindi and Devanagari content
summary: "Noto Sans Devanagari for Devanagari text, Inter for English interface text."
moods: [neutral, readable]
products: [hindi, marathi, devanagari, nepali]
tags: [font, typography, pairing, offline]
density: any
dependencies: []
licence: OFL-1.1
source: "bundled fonts Noto Sans Devanagari and Inter (Fontsource, 5.3.0)"
preview: assets/preview/pair-hindi.jpg
tested: both fonts and their CSS checked by tests/test_fonts.py (D-268)
files:
  - from: fonts/noto-sans-devanagari/noto-sans-devanagari-devanagari-wght-normal.woff2
    to: public/fonts/noto-sans-devanagari-devanagari-wght-normal.woff2
  - from: fonts/noto-sans-devanagari/noto-sans-devanagari-latin-wght-normal.woff2
    to: public/fonts/noto-sans-devanagari-latin-wght-normal.woff2
  - from: fonts/noto-sans-devanagari/noto-sans-devanagari.css
    to: src/fonts/noto-sans-devanagari.css
  - from: fonts/noto-sans-devanagari/noto-sans-devanagari-OFL.txt
    to: public/fonts/noto-sans-devanagari-OFL.txt
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
---

## Hindi and Devanagari content

Noto Sans Devanagari for Devanagari text, Inter for English interface text.

Heading font: **Noto Sans Devanagari** (`font-noto-sans-devanagari`). Text font: **Inter** (`font-inter`). Use `lang="hi"` on Hindi elements; line-height 1.7 and no negative tracking.

```css
@import "./fonts/noto-sans-devanagari.css";
@import "./fonts/inter.css";
@theme {
  --font-display: "Noto Sans Devanagari Variable", ui-sans-serif, system-ui, sans-serif;
  --font-sans: "Inter Variable", ui-sans-serif, system-ui, sans-serif;
}
```

Use `font-display` (Tailwind class `font-display`) for headings and the default `font-sans` for the rest. Both fonts are
bundled, so nothing loads from the internet.
