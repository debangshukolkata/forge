---
id: mi-input-prefix-focus
type: effect
title: "Prefix that lights up"
summary: "A field with a currency or unit prefix that takes the accent colour when the field is focused."
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
preview: assets/preview/mi-input-prefix-focus.jpg
---

## Prefix that lights up

A field with a currency or unit prefix that takes the accent colour when the field is focused. The prefix is decoration: put the unit in the label too for screen readers.

Markup:

```html
<div class="mi-input-prefix-focus"><i>&euro;</i><input inputmode="decimal" aria-label="Amount" placeholder="0.00"></div>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
