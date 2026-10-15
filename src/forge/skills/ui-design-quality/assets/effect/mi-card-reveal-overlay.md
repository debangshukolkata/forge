---
id: mi-card-reveal-overlay
type: effect
title: "Slide-up details"
summary: "A picture card whose details slide up from the bottom on hover or focus."
moods: [clear, modern]
products: [apps, forms, marketing]
tags: [animation, motion, micro-interaction, card, css, no build step]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (micro-interaction kit, D-382)"
tested: "demo page in Edge: the action (hover, focus, check, press or invalid) changes the probed property or the animation runs, and it is switched off under reduced motion (tests/test_micro_effects.py, D-382)"
files:
  - from: recipes/motion-micro.css
    to: src/motion-micro.css
---

## Slide-up details

A picture card whose details slide up from the bottom on hover or focus. The details must also be reachable without hover (they are, on focus); on a phone show them always.

Markup:

```html
<article class="mi-card-reveal-overlay" tabindex="0"><div class="o"><b>Harbour Pickup</b><p>Opens 08:00 on weekdays</p></div></article>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
