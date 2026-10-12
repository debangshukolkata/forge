---
id: font-outfit
type: font
title: Outfit
summary: "Outfit (sans, weights 100 900) bundled offline: Geometric sans with round forms; strong at large sizes."
moods: [geometric, playful, clean]
products: [landing, apps, brands]
tags: [font, typography, sans, offline, woff2]
density: any
dependencies: []
licence: OFL-1.1
source: "Fontsource @fontsource-variable/outfit 5.3.0 (copyright holders in the OFL text)"
tested: woff2 files and CSS checked by tests/test_fonts.py; rendered in Edge in the offline font test page (D-268)
files:
  - from: fonts/outfit/outfit-latin-wght-normal.woff2
    to: public/fonts/outfit-latin-wght-normal.woff2
  - from: fonts/outfit/outfit.css
    to: src/fonts/outfit.css
  - from: fonts/outfit/outfit-OFL.txt
    to: public/fonts/outfit-OFL.txt
---

## Outfit

Geometric sans with round forms; strong at large sizes. Weights 100 900. Category: sans. Role: heading.

Use: import the stylesheet once, then name the family in the theme (Tailwind v4):

```css
@import "./fonts/outfit.css";   /* in your main CSS file, before or after @import "tailwindcss" */
@theme {
  --font-sans: "Outfit Variable", ui-sans-serif, system-ui, sans-serif;
}
```

The font files are copied to `public/fonts/` and served from `/fonts/...`; nothing is fetched from the internet, so the page
looks the same on a laptop with no connection. Keep the fallback stack: it shows while the font loads (`font-display: swap`).
Licence: SIL Open Font License 1.1; the copyright holders are named in the licence text copied next to the files (`public/fonts/outfit-OFL.txt`).
