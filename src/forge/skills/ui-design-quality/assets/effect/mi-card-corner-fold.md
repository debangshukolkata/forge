---
id: mi-card-corner-fold
type: effect
title: "Folding corner"
summary: "A card with a corner that folds open a little on hover."
moods: [editorial, calm]
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

## Folding corner

A card with a corner that folds open a little on hover. A document metaphor: invoices, notes, letters.

Markup:

```html
<article class="mi-card-corner-fold"><i></i><h3>Invoice 2025-03</h3><p>Paid on 3 March</p></article>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
