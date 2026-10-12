---
id: font-inter
type: font
title: Inter
summary: "Inter (sans, weights 100 900) bundled offline: The safe default for interfaces and body text; excellent at small sizes."
moods: [clean, neutral, modern]
products: [saas, dashboards, forms, any app]
tags: [font, typography, sans, offline, woff2]
density: any
dependencies: []
licence: OFL-1.1
source: "Fontsource @fontsource-variable/inter 5.3.0 (copyright holders in the OFL text)"
tested: woff2 files and CSS checked by tests/test_fonts.py; rendered in Edge in the offline font test page (D-268)
files:
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
---

## Inter

The safe default for interfaces and body text; excellent at small sizes. Weights 100 900. Category: sans. Role: body.

Use: import the stylesheet once, then name the family in the theme (Tailwind v4):

```css
@import "./fonts/inter.css";   /* in your main CSS file, before or after @import "tailwindcss" */
@theme {
  --font-sans: "Inter Variable", ui-sans-serif, system-ui, sans-serif;
}
```

The font files are copied to `public/fonts/` and served from `/fonts/...`; nothing is fetched from the internet, so the page
looks the same on a laptop with no connection. Keep the fallback stack: it shows while the font loads (`font-display: swap`).
Licence: SIL Open Font License 1.1; the copyright holders are named in the licence text copied next to the files (`public/fonts/inter-OFL.txt`).
