---
id: font-nunito
type: font
title: Nunito
summary: "Nunito (rounded, weights 200 1000) bundled offline: Rounded terminals make it friendly and approachable."
moods: [friendly, playful, soft]
products: [kids, food, community, consumer apps]
tags: [font, typography, rounded, offline, woff2]
density: any
dependencies: []
licence: OFL-1.1
source: "Fontsource @fontsource-variable/nunito 5.3.0 (copyright holders in the OFL text)"
tested: woff2 files and CSS checked by tests/test_fonts.py; rendered in Edge in the offline font test page (D-268)
files:
  - from: fonts/nunito/nunito-latin-wght-normal.woff2
    to: public/fonts/nunito-latin-wght-normal.woff2
  - from: fonts/nunito/nunito.css
    to: src/fonts/nunito.css
  - from: fonts/nunito/nunito-OFL.txt
    to: public/fonts/nunito-OFL.txt
---

## Nunito

Rounded terminals make it friendly and approachable. Weights 200 1000. Category: rounded. Role: heading or body.

Use: import the stylesheet once, then name the family in the theme (Tailwind v4):

```css
@import "./fonts/nunito.css";   /* in your main CSS file, before or after @import "tailwindcss" */
@theme {
  --font-sans: "Nunito Variable", ui-rounded, system-ui, sans-serif;
}
```

The font files are copied to `public/fonts/` and served from `/fonts/...`; nothing is fetched from the internet, so the page
looks the same on a laptop with no connection. Keep the fallback stack: it shows while the font loads (`font-display: swap`).
Licence: SIL Open Font License 1.1; the copyright holders are named in the licence text copied next to the files (`public/fonts/nunito-OFL.txt`).
