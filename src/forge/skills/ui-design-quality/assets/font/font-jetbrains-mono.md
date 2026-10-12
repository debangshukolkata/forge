---
id: font-jetbrains-mono
type: font
title: JetBrains Mono
summary: "JetBrains Mono (mono, weights 100 800) bundled offline: Monospace made for code; also works as a retro heading face."
moods: [technical, retro, developer]
products: [developer tools, terminals, code, dashboards]
tags: [font, typography, mono, offline, woff2]
density: any
dependencies: []
licence: OFL-1.1
source: "Fontsource @fontsource-variable/jetbrains-mono 5.3.0 (copyright holders in the OFL text)"
tested: woff2 files and CSS checked by tests/test_fonts.py; rendered in Edge in the offline font test page (D-268)
files:
  - from: fonts/jetbrains-mono/jetbrains-mono-latin-wght-normal.woff2
    to: public/fonts/jetbrains-mono-latin-wght-normal.woff2
  - from: fonts/jetbrains-mono/jetbrains-mono.css
    to: src/fonts/jetbrains-mono.css
  - from: fonts/jetbrains-mono/jetbrains-mono-OFL.txt
    to: public/fonts/jetbrains-mono-OFL.txt
---

## JetBrains Mono

Monospace made for code; also works as a retro heading face. Weights 100 800. Category: mono. Role: code or heading.

Use: import the stylesheet once, then name the family in the theme (Tailwind v4):

```css
@import "./fonts/jetbrains-mono.css";   /* in your main CSS file, before or after @import "tailwindcss" */
@theme {
  --font-mono: "JetBrains Mono Variable", ui-monospace, Consolas, monospace;
}
```

The font files are copied to `public/fonts/` and served from `/fonts/...`; nothing is fetched from the internet, so the page
looks the same on a laptop with no connection. Keep the fallback stack: it shows while the font loads (`font-display: swap`).
Licence: SIL Open Font License 1.1; the copyright holders are named in the licence text copied next to the files (`public/fonts/jetbrains-mono-OFL.txt`).
