---
id: font-lora
type: font
title: Lora
summary: "Lora (serif, weights 400 700) bundled offline: Readable text serif for long reading."
moods: [calm, literary, readable]
products: [articles, blogs, journals]
tags: [font, typography, serif, offline, woff2]
density: any
dependencies: []
licence: OFL-1.1
source: "Fontsource @fontsource-variable/lora 5.3.0 (copyright holders in the OFL text)"
tested: woff2 files and CSS checked by tests/test_fonts.py; rendered in Edge in the offline font test page (D-268)
files:
  - from: fonts/lora/lora-latin-wght-normal.woff2
    to: public/fonts/lora-latin-wght-normal.woff2
  - from: fonts/lora/lora.css
    to: src/fonts/lora.css
  - from: fonts/lora/lora-OFL.txt
    to: public/fonts/lora-OFL.txt
---

## Lora

Readable text serif for long reading. Weights 400 700. Category: serif. Role: heading or body.

Use: import the stylesheet once, then name the family in the theme (Tailwind v4):

```css
@import "./fonts/lora.css";   /* in your main CSS file, before or after @import "tailwindcss" */
@theme {
  --font-serif: "Lora Variable", ui-serif, Georgia, serif;
}
```

The font files are copied to `public/fonts/` and served from `/fonts/...`; nothing is fetched from the internet, so the page
looks the same on a laptop with no connection. Keep the fallback stack: it shows while the font loads (`font-display: swap`).
Licence: SIL Open Font License 1.1; the copyright holders are named in the licence text copied next to the files (`public/fonts/lora-OFL.txt`).
