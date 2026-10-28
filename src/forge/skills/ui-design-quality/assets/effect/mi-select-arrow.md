---
id: mi-select-arrow
type: effect
title: "Turning select arrow"
summary: "A select whose chevron turns over when the field is focused or open."
moods: [clear, modern]
products: [apps, forms, marketing]
tags: [animation, motion, micro-interaction, input, css, no build step]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (micro-interaction kit, D-382)"
tested: "demo page in Edge: the action (hover, focus, check, press or invalid) changes the probed property or the animation runs, and it is switched off under reduced motion (tests/test_micro_effects.py, D-382)"
files:
  - from: recipes/motion-micro.css
    to: src/motion-micro.css
preview: assets/preview/mi-select-arrow.jpg
---

## Turning select arrow

A select whose chevron turns over when the field is focused or open. A native select underneath: it keeps its keyboard and phone behaviour.

Markup:

```html
<div class="mi-select-arrow"><select aria-label="Country"><option>Germany</option><option>France</option></select><i></i></div>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
