---
id: font-fraunces
type: font
title: Fraunces
summary: "Fraunces (serif, weights 100 900) bundled offline: Soft old-style serif with personality; the warm editorial headline face."
moods: [warm, editorial, characterful]
products: [charity, health, boutique, food]
tags: [font, typography, serif, offline, woff2]
density: any
dependencies: []
licence: OFL-1.1
source: "Fontsource @fontsource-variable/fraunces 5.3.0 (copyright holders in the OFL text)"
tested: woff2 files and CSS checked by tests/test_fonts.py; rendered in Edge in the offline font test page (D-268)
files:
  - from: fonts/fraunces/fraunces-latin-wght-normal.woff2
    to: public/fonts/fraunces-latin-wght-normal.woff2
  - from: fonts/fraunces/fraunces.css
    to: src/fonts/fraunces.css
  - from: fonts/fraunces/fraunces-OFL.txt
    to: public/fonts/fraunces-OFL.txt
---

## Fraunces

Soft old-style serif with personality; the warm editorial headline face. Weights 100 900. Category: serif. Role: heading.

Use: import the stylesheet once, then name the family in the theme (Tailwind v4):

```css
@import "./fonts/fraunces.css";   /* in your main CSS file, before or after @import "tailwindcss" */
@theme {
  --font-serif: "Fraunces Variable", ui-serif, Georgia, serif;
}
```

The font files are copied to `public/fonts/` and served from `/fonts/...`; nothing is fetched from the internet, so the page
looks the same on a laptop with no connection. Keep the fallback stack: it shows while the font loads (`font-display: swap`).
Licence: SIL Open Font License 1.1; the copyright holders are named in the licence text copied next to the files (`public/fonts/fraunces-OFL.txt`).
