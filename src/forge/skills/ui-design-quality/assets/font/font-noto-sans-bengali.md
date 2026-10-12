---
id: font-noto-sans-bengali
type: font
title: Noto Sans Bengali
summary: "Noto Sans Bengali (indic, weights 100 900) bundled offline: Bengali script with a matching Latin; use when the page has Bengali text."
moods: [neutral, readable]
products: [bengali, bangla, west bengal, bangladesh]
tags: [font, typography, indic, offline, woff2]
density: any
dependencies: []
licence: OFL-1.1
source: "Fontsource @fontsource-variable/noto-sans-bengali 5.3.0 (copyright holders in the OFL text)"
tested: woff2 files and CSS checked by tests/test_fonts.py; rendered in Edge in the offline font test page (D-268)
files:
  - from: fonts/noto-sans-bengali/noto-sans-bengali-bengali-wght-normal.woff2
    to: public/fonts/noto-sans-bengali-bengali-wght-normal.woff2
  - from: fonts/noto-sans-bengali/noto-sans-bengali-latin-wght-normal.woff2
    to: public/fonts/noto-sans-bengali-latin-wght-normal.woff2
  - from: fonts/noto-sans-bengali/noto-sans-bengali.css
    to: src/fonts/noto-sans-bengali.css
  - from: fonts/noto-sans-bengali/noto-sans-bengali-OFL.txt
    to: public/fonts/noto-sans-bengali-OFL.txt
---

## Noto Sans Bengali

Bengali script with a matching Latin; use when the page has Bengali text. Weights 100 900. Category: indic. Role: body.

Use: import the stylesheet once, then name the family in the theme (Tailwind v4):

```css
@import "./fonts/noto-sans-bengali.css";   /* in your main CSS file, before or after @import "tailwindcss" */
@theme {
  --font-sans: "Noto Sans Bengali Variable", system-ui, sans-serif;
}
```

The font files are copied to `public/fonts/` and served from `/fonts/...`; nothing is fetched from the internet, so the page
looks the same on a laptop with no connection. Keep the fallback stack: it shows while the font loads (`font-display: swap`).
Licence: SIL Open Font License 1.1; the copyright holders are named in the licence text copied next to the files (`public/fonts/noto-sans-bengali-OFL.txt`).
