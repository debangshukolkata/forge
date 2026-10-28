---
id: mi-loader-ripple
type: effect
title: "Ripple"
summary: "Two rings that expand and fade from a centre point."
moods: [clear, modern]
products: [apps, forms, marketing]
tags: [animation, motion, micro-interaction, loader, css, no build step]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (micro-interaction kit, D-382)"
tested: "demo page in Edge: the action (hover, focus, check, press or invalid) changes the probed property or the animation runs, and it is switched off under reduced motion (tests/test_micro_effects.py, D-382)"
files:
  - from: recipes/motion-micro.css
    to: src/motion-micro.css
preview: assets/preview/mi-loader-ripple.jpg
---

## Ripple

Two rings that expand and fade from a centre point. A calm indicator for connecting, listening or searching.

Markup:

```html
<span class="mi-loader-ripple" role="status" aria-label="Loading"><i></i><i></i></span>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
