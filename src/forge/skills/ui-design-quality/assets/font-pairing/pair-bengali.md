---
id: pair-bengali
type: font-pairing
title: Bengali content
summary: "Noto Sans Bengali for Bengali text (it includes a matching Latin), Inter for English interface text."
moods: [neutral, readable]
products: [bengali, bangla, west bengal, bangladesh]
tags: [font, typography, pairing, offline]
density: any
dependencies: []
licence: OFL-1.1
source: "bundled fonts Noto Sans Bengali and Inter (Fontsource, 5.3.0)"
tested: both fonts and their CSS checked by tests/test_fonts.py (D-268)
files:
  - from: fonts/noto-sans-bengali/noto-sans-bengali-bengali-wght-normal.woff2
    to: public/fonts/noto-sans-bengali-bengali-wght-normal.woff2
  - from: fonts/noto-sans-bengali/noto-sans-bengali-latin-wght-normal.woff2
    to: public/fonts/noto-sans-bengali-latin-wght-normal.woff2
  - from: fonts/noto-sans-bengali/noto-sans-bengali.css
    to: src/fonts/noto-sans-bengali.css
  - from: fonts/noto-sans-bengali/noto-sans-bengali-OFL.txt
    to: public/fonts/noto-sans-bengali-OFL.txt
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
---

## Bengali content

Noto Sans Bengali for Bengali text (it includes a matching Latin), Inter for English interface text.

Heading font: **Noto Sans Bengali** (`font-noto-sans-bengali`). Text font: **Inter** (`font-inter`). Use `lang="bn"` on Bengali elements; line-height 1.7 and no negative tracking for Bengali.

```css
@import "./fonts/noto-sans-bengali.css";
@import "./fonts/inter.css";
@theme {
  --font-display: "Noto Sans Bengali Variable", ui-sans-serif, system-ui, sans-serif;
  --font-sans: "Inter Variable", ui-sans-serif, system-ui, sans-serif;
}
```

Use `font-display` (Tailwind class `font-display`) for headings and the default `font-sans` for the rest. Both fonts are
bundled, so nothing loads from the internet.
