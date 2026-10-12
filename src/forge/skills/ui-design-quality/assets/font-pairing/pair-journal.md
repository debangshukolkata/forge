---
id: pair-journal
type: font-pairing
title: Journal
summary: "Lora for article text and headings, Plus Jakarta Sans for interface labels."
moods: [calm, literary, readable]
products: [articles, blogs, journals]
tags: [font, typography, pairing, offline]
density: any
dependencies: []
licence: OFL-1.1
source: "bundled fonts Lora and Plus Jakarta Sans (Fontsource, 5.3.0)"
tested: both fonts and their CSS checked by tests/test_fonts.py (D-268)
files:
  - from: fonts/lora/lora-latin-wght-normal.woff2
    to: public/fonts/lora-latin-wght-normal.woff2
  - from: fonts/lora/lora.css
    to: src/fonts/lora.css
  - from: fonts/lora/lora-OFL.txt
    to: public/fonts/lora-OFL.txt
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans-latin-wght-normal.woff2
    to: public/fonts/plus-jakarta-sans-latin-wght-normal.woff2
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans.css
    to: src/fonts/plus-jakarta-sans.css
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans-OFL.txt
    to: public/fonts/plus-jakarta-sans-OFL.txt
---

## Journal

Lora for article text and headings, Plus Jakarta Sans for interface labels.

Heading font: **Lora** (`font-lora`). Text font: **Plus Jakarta Sans** (`font-plus-jakarta-sans`). Article body Lora 18 to 20 px, measure 60 to 70 characters, line-height 1.7.

```css
@import "./fonts/lora.css";
@import "./fonts/plus-jakarta-sans.css";
@theme {
  --font-display: "Lora Variable", ui-sans-serif, system-ui, sans-serif;
  --font-sans: "Plus Jakarta Sans Variable", ui-sans-serif, system-ui, sans-serif;
}
```

Use `font-display` (Tailwind class `font-display`) for headings and the default `font-sans` for the rest. Both fonts are
bundled, so nothing loads from the internet.
