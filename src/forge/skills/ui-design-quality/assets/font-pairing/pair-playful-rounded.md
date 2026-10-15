---
id: pair-playful-rounded
type: font-pairing
title: Playful rounded
summary: "Nunito headings (weight 800) with DM Sans text. Pairs with `dir-playful-friendly`."
moods: [playful, friendly, soft]
products: [kids, food, community, consumer apps]
tags: [font, typography, pairing, offline]
density: any
dependencies: []
licence: OFL-1.1
source: "bundled fonts Nunito and DM Sans (Fontsource, 5.3.0)"
preview: assets/preview/pair-playful-rounded.jpg
tested: both fonts and their CSS checked by tests/test_fonts.py (D-268)
files:
  - from: fonts/nunito/nunito-latin-wght-normal.woff2
    to: public/fonts/nunito-latin-wght-normal.woff2
  - from: fonts/nunito/nunito.css
    to: src/fonts/nunito.css
  - from: fonts/nunito/nunito-OFL.txt
    to: public/fonts/nunito-OFL.txt
  - from: fonts/dm-sans/dm-sans-latin-wght-normal.woff2
    to: public/fonts/dm-sans-latin-wght-normal.woff2
  - from: fonts/dm-sans/dm-sans.css
    to: src/fonts/dm-sans.css
  - from: fonts/dm-sans/dm-sans-OFL.txt
    to: public/fonts/dm-sans-OFL.txt
---

## Playful rounded

Nunito headings (weight 800) with DM Sans text. Pairs with `dir-playful-friendly`.

Heading font: **Nunito** (`font-nunito`). Text font: **DM Sans** (`font-dm-sans`). Big rounded headings 40 to 56 px; generous line-height 1.6 for body.

```css
@import "./fonts/nunito.css";
@import "./fonts/dm-sans.css";
@theme {
  --font-display: "Nunito Variable", ui-sans-serif, system-ui, sans-serif;
  --font-sans: "DM Sans Variable", ui-sans-serif, system-ui, sans-serif;
}
```

Use `font-display` (Tailwind class `font-display`) for headings and the default `font-sans` for the rest. Both fonts are
bundled, so nothing loads from the internet.
