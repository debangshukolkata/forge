---
id: mi-card-lift
type: effect
title: "Lift"
summary: "A card that rises and gains a deeper shadow on hover."
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
preview: assets/preview/mi-card-lift.jpg
---

## Lift

A card that rises and gains a deeper shadow on hover. For cards that are links: make the whole card clickable with a stretched link, not only the title.

Markup:

```html
<article class="mi-card-lift"><h3>Riverside Depot</h3><p>Open until 20:00</p><a href="#">Details</a></article>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
