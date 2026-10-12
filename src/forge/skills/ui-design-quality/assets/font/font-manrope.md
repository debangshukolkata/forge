---
id: font-manrope
type: font
title: Manrope
summary: "Manrope (sans, weights 200 800) bundled offline: Semi-condensed modern sans with an engineered feel."
moods: [modern, technical, precise]
products: [fintech, saas, dashboards]
tags: [font, typography, sans, offline, woff2]
density: any
dependencies: []
licence: OFL-1.1
source: "Fontsource @fontsource-variable/manrope 5.3.0 (copyright holders in the OFL text)"
tested: woff2 files and CSS checked by tests/test_fonts.py; rendered in Edge in the offline font test page (D-268)
files:
  - from: fonts/manrope/manrope-latin-wght-normal.woff2
    to: public/fonts/manrope-latin-wght-normal.woff2
  - from: fonts/manrope/manrope.css
    to: src/fonts/manrope.css
  - from: fonts/manrope/manrope-OFL.txt
    to: public/fonts/manrope-OFL.txt
---

## Manrope

Semi-condensed modern sans with an engineered feel. Weights 200 800. Category: sans. Role: heading or body.

Use: import the stylesheet once, then name the family in the theme (Tailwind v4):

```css
@import "./fonts/manrope.css";   /* in your main CSS file, before or after @import "tailwindcss" */
@theme {
  --font-sans: "Manrope Variable", ui-sans-serif, system-ui, sans-serif;
}
```

The font files are copied to `public/fonts/` and served from `/fonts/...`; nothing is fetched from the internet, so the page
looks the same on a laptop with no connection. Keep the fallback stack: it shows while the font loads (`font-display: swap`).
Licence: SIL Open Font License 1.1; the copyright holders are named in the licence text copied next to the files (`public/fonts/manrope-OFL.txt`).
