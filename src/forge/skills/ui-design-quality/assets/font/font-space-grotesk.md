---
id: font-space-grotesk
type: font
title: Space Grotesk
summary: "Space Grotesk (sans, weights 300 700) bundled offline: Distinctive grotesk with character; set large and tight for posters."
moods: [bold, techy, quirky]
products: [campaigns, developer tools, posters]
tags: [font, typography, sans, offline, woff2]
density: any
dependencies: []
licence: OFL-1.1
source: "Fontsource @fontsource-variable/space-grotesk 5.3.0 (copyright holders in the OFL text)"
tested: woff2 files and CSS checked by tests/test_fonts.py; rendered in Edge in the offline font test page (D-268)
files:
  - from: fonts/space-grotesk/space-grotesk-latin-wght-normal.woff2
    to: public/fonts/space-grotesk-latin-wght-normal.woff2
  - from: fonts/space-grotesk/space-grotesk.css
    to: src/fonts/space-grotesk.css
  - from: fonts/space-grotesk/space-grotesk-OFL.txt
    to: public/fonts/space-grotesk-OFL.txt
---

## Space Grotesk

Distinctive grotesk with character; set large and tight for posters. Weights 300 700. Category: sans. Role: heading.

Use: import the stylesheet once, then name the family in the theme (Tailwind v4):

```css
@import "./fonts/space-grotesk.css";   /* in your main CSS file, before or after @import "tailwindcss" */
@theme {
  --font-sans: "Space Grotesk Variable", ui-sans-serif, system-ui, sans-serif;
}
```

The font files are copied to `public/fonts/` and served from `/fonts/...`; nothing is fetched from the internet, so the page
looks the same on a laptop with no connection. Keep the fallback stack: it shows while the font loads (`font-display: swap`).
Licence: SIL Open Font License 1.1; the copyright holders are named in the licence text copied next to the files (`public/fonts/space-grotesk-OFL.txt`).
