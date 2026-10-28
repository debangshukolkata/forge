---
id: css-depth-surfaces-effects
type: css-technique
title: "Depth, surfaces, effects"
summary: "Snippets for depth, surfaces, effects."
moods: [shadows]
products: [stylesheet]
tags: [css, technique]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (recipes/css-techniques.md)"
tested: snippets follow current Chromium (Edge) behaviour; checked when the recipe was written (D-251)
---

## Depth, surfaces, effects
```css
.shadow-layered { box-shadow: 0 1px 1px rgb(0 0 0 / .05), 0 4px 8px rgb(0 0 0 / .05), 0 16px 32px rgb(0 0 0 / .08); }
.ring-soft { box-shadow: 0 0 0 1px rgb(0 0 0 / .06), 0 8px 24px -8px rgb(0 0 0 / .18); }
.mask-fade { mask-image: linear-gradient(to bottom, #000 70%, transparent); }    /* fade an image/list edge */
.noise::after { /* see .grain in motion.css */ }
.text-gradient { background: linear-gradient(90deg, #6366f1, #ec4899); -webkit-background-clip: text; color: transparent; }
.blur-bg { backdrop-filter: blur(14px) saturate(160%); }                      /* needs a translucent background */
.dots { background-image: radial-gradient(rgb(0 0 0 / .12) 1px, transparent 1px); background-size: 20px 20px; }
.grid-lines { background-image: linear-gradient(rgb(0 0 0 / .05) 1px, transparent 1px), linear-gradient(90deg, rgb(0 0 0 / .05) 1px, transparent 1px); background-size: 40px 40px; }
.hero-bg { background: radial-gradient(60rem 30rem at 80% -10%, color-mix(in oklab, var(--accent) 22%, transparent), transparent), var(--bg); }
```
