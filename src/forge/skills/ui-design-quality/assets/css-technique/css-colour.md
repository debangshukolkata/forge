---
id: css-colour
type: css-technique
title: "Colour"
summary: "Snippets for colour."
moods: [oklch]
products: [web, landing, app, dashboard]
tags: [css, html, native, no dependency]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (recipes/css-techniques.md)"
tested: snippets follow current Chromium (Edge) behaviour; checked when the recipe was written (D-251)
---

## Colour
```css
:root { --accent: oklch(55% 0.2 25); }                                       /* perceptual colour: easy tints and shades */
.btn:hover { background: color-mix(in oklab, var(--accent) 88%, black); }    /* derive hover/tint without extra tokens */
.tint { background: color-mix(in oklab, var(--accent) 10%, white); }
.gradient { background: linear-gradient(135deg in oklch, oklch(70% .2 25), oklch(60% .22 330)); }  /* smooth, no grey mud */
:root { color-scheme: light dark; }                                           /* native form controls follow the theme */
@media (prefers-color-scheme: dark) { :root { --bg: #0b0d12; --fg: #e5e7eb; } }
/* manual toggle: set data-theme on <html> and define the same tokens under [data-theme="dark"] */
```
