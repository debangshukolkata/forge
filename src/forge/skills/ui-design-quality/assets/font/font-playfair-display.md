---
id: font-playfair-display
type: font
title: Playfair Display
summary: "Playfair Display (serif, weights 400 900) bundled offline: High-contrast display serif; use large, never for small text."
moods: [elegant, luxury, editorial]
products: [portfolio, fashion, hospitality]
tags: [font, typography, serif, offline, woff2]
density: any
dependencies: []
licence: OFL-1.1
source: "Fontsource @fontsource-variable/playfair-display 5.3.0 (copyright holders in the OFL text)"
tested: woff2 files and CSS checked by tests/test_fonts.py; rendered in Edge in the offline font test page (D-268)
files:
  - from: fonts/playfair-display/playfair-display-latin-wght-normal.woff2
    to: public/fonts/playfair-display-latin-wght-normal.woff2
  - from: fonts/playfair-display/playfair-display.css
    to: src/fonts/playfair-display.css
  - from: fonts/playfair-display/playfair-display-OFL.txt
    to: public/fonts/playfair-display-OFL.txt
---

## Playfair Display

High-contrast display serif; use large, never for small text. Weights 400 900. Category: serif. Role: heading.

Use: import the stylesheet once, then name the family in the theme (Tailwind v4):

```css
@import "./fonts/playfair-display.css";   /* in your main CSS file, before or after @import "tailwindcss" */
@theme {
  --font-serif: "Playfair Display Variable", ui-serif, Georgia, serif;
}
```

The font files are copied to `public/fonts/` and served from `/fonts/...`; nothing is fetched from the internet, so the page
looks the same on a laptop with no connection. Keep the fallback stack: it shows while the font loads (`font-display: swap`).
Licence: SIL Open Font License 1.1; the copyright holders are named in the licence text copied next to the files (`public/fonts/playfair-display-OFL.txt`).
