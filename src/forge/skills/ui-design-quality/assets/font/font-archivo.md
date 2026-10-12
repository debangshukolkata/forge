---
id: font-archivo
type: font
title: Archivo
summary: "Archivo (sans, weights 100 900) bundled offline: Sturdy grotesque with heavy weights for loud headlines."
moods: [bold, strong, grotesque]
products: [campaigns, sport, news]
tags: [font, typography, sans, offline, woff2]
density: any
dependencies: []
licence: OFL-1.1
source: "Fontsource @fontsource-variable/archivo 5.3.0 (copyright holders in the OFL text)"
tested: woff2 files and CSS checked by tests/test_fonts.py; rendered in Edge in the offline font test page (D-268)
files:
  - from: fonts/archivo/archivo-latin-wght-normal.woff2
    to: public/fonts/archivo-latin-wght-normal.woff2
  - from: fonts/archivo/archivo.css
    to: src/fonts/archivo.css
  - from: fonts/archivo/archivo-OFL.txt
    to: public/fonts/archivo-OFL.txt
---

## Archivo

Sturdy grotesque with heavy weights for loud headlines. Weights 100 900. Category: sans. Role: heading.

Use: import the stylesheet once, then name the family in the theme (Tailwind v4):

```css
@import "./fonts/archivo.css";   /* in your main CSS file, before or after @import "tailwindcss" */
@theme {
  --font-sans: "Archivo Variable", ui-sans-serif, system-ui, sans-serif;
}
```

The font files are copied to `public/fonts/` and served from `/fonts/...`; nothing is fetched from the internet, so the page
looks the same on a laptop with no connection. Keep the fallback stack: it shows while the font loads (`font-display: swap`).
Licence: SIL Open Font License 1.1; the copyright holders are named in the licence text copied next to the files (`public/fonts/archivo-OFL.txt`).
