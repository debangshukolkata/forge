---
id: font-plus-jakarta-sans
type: font
title: Plus Jakarta Sans
summary: "Plus Jakarta Sans (sans, weights 200 800) bundled offline: Rounded geometric feel with warmth; good for headings and body together."
moods: [friendly, modern, polished]
products: [saas, startups, landing]
tags: [font, typography, sans, offline, woff2]
density: any
dependencies: []
licence: OFL-1.1
source: "Fontsource @fontsource-variable/plus-jakarta-sans 5.3.0 (copyright holders in the OFL text)"
tested: woff2 files and CSS checked by tests/test_fonts.py; rendered in Edge in the offline font test page (D-268)
files:
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans-latin-wght-normal.woff2
    to: public/fonts/plus-jakarta-sans-latin-wght-normal.woff2
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans.css
    to: src/fonts/plus-jakarta-sans.css
  - from: fonts/plus-jakarta-sans/plus-jakarta-sans-OFL.txt
    to: public/fonts/plus-jakarta-sans-OFL.txt
---

## Plus Jakarta Sans

Rounded geometric feel with warmth; good for headings and body together. Weights 200 800. Category: sans. Role: heading or body.

Use: import the stylesheet once, then name the family in the theme (Tailwind v4):

```css
@import "./fonts/plus-jakarta-sans.css";   /* in your main CSS file, before or after @import "tailwindcss" */
@theme {
  --font-sans: "Plus Jakarta Sans Variable", ui-sans-serif, system-ui, sans-serif;
}
```

The font files are copied to `public/fonts/` and served from `/fonts/...`; nothing is fetched from the internet, so the page
looks the same on a laptop with no connection. Keep the fallback stack: it shows while the font loads (`font-display: swap`).
Licence: SIL Open Font License 1.1; the copyright holders are named in the licence text copied next to the files (`public/fonts/plus-jakarta-sans-OFL.txt`).
