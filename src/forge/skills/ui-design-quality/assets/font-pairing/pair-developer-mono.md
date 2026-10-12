---
id: pair-developer-mono
type: font-pairing
title: Developer mono
summary: "JetBrains Mono for headings, code and numbers, Inter for text. Pairs with `dir-retro-terminal` and `dir-dark-dashboard`."
moods: [technical, retro, dark]
products: [developer tools, terminals, dark dashboards]
tags: [font, typography, pairing, offline]
density: any
dependencies: []
licence: OFL-1.1
source: "bundled fonts JetBrains Mono and Inter (Fontsource, 5.3.0)"
tested: both fonts and their CSS checked by tests/test_fonts.py (D-268)
files:
  - from: fonts/jetbrains-mono/jetbrains-mono-latin-wght-normal.woff2
    to: public/fonts/jetbrains-mono-latin-wght-normal.woff2
  - from: fonts/jetbrains-mono/jetbrains-mono.css
    to: src/fonts/jetbrains-mono.css
  - from: fonts/jetbrains-mono/jetbrains-mono-OFL.txt
    to: public/fonts/jetbrains-mono-OFL.txt
  - from: fonts/inter/inter-latin-wght-normal.woff2
    to: public/fonts/inter-latin-wght-normal.woff2
  - from: fonts/inter/inter.css
    to: src/fonts/inter.css
  - from: fonts/inter/inter-OFL.txt
    to: public/fonts/inter-OFL.txt
---

## Developer mono

JetBrains Mono for headings, code and numbers, Inter for text. Pairs with `dir-retro-terminal` and `dir-dark-dashboard`.

Heading font: **JetBrains Mono** (`font-jetbrains-mono`). Text font: **Inter** (`font-inter`). Mono headings 20 to 32 px; code blocks 14 px.

```css
@import "./fonts/jetbrains-mono.css";
@import "./fonts/inter.css";
@theme {
  --font-display: "JetBrains Mono Variable", ui-sans-serif, system-ui, sans-serif;
  --font-sans: "Inter Variable", ui-sans-serif, system-ui, sans-serif;
}
```

Use `font-display` (Tailwind class `font-display`) for headings and the default `font-sans` for the rest. Both fonts are
bundled, so nothing loads from the internet.
