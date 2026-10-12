---
id: font-dm-sans
type: font
title: DM Sans
summary: "DM Sans (sans, weights 100 1000) bundled offline: Low-contrast geometric sans; calm and legible."
moods: [clean, friendly, geometric]
products: [landing, portfolio, editorial]
tags: [font, typography, sans, offline, woff2]
density: any
dependencies: []
licence: OFL-1.1
source: "Fontsource @fontsource-variable/dm-sans 5.3.0 (copyright holders in the OFL text)"
tested: woff2 files and CSS checked by tests/test_fonts.py; rendered in Edge in the offline font test page (D-268)
files:
  - from: fonts/dm-sans/dm-sans-latin-wght-normal.woff2
    to: public/fonts/dm-sans-latin-wght-normal.woff2
  - from: fonts/dm-sans/dm-sans.css
    to: src/fonts/dm-sans.css
  - from: fonts/dm-sans/dm-sans-OFL.txt
    to: public/fonts/dm-sans-OFL.txt
---

## DM Sans

Low-contrast geometric sans; calm and legible. Weights 100 1000. Category: sans. Role: heading or body.

Use: import the stylesheet once, then name the family in the theme (Tailwind v4):

```css
@import "./fonts/dm-sans.css";   /* in your main CSS file, before or after @import "tailwindcss" */
@theme {
  --font-sans: "DM Sans Variable", ui-sans-serif, system-ui, sans-serif;
}
```

The font files are copied to `public/fonts/` and served from `/fonts/...`; nothing is fetched from the internet, so the page
looks the same on a laptop with no connection. Keep the fallback stack: it shows while the font loads (`font-display: swap`).
Licence: SIL Open Font License 1.1; the copyright holders are named in the licence text copied next to the files (`public/fonts/dm-sans-OFL.txt`).
