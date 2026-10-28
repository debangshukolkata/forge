---
id: mi-input-ring
type: effect
title: "Focus ring"
summary: "A soft ring that grows around a field when it is focused."
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
preview: assets/preview/mi-input-ring.jpg
---

## Focus ring

A soft ring that grows around a field when it is focused. The ring is the focus indicator: do not remove it.

Markup:

```html
<input class="mi-input-ring" aria-label="Postcode" placeholder="Postcode">
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
