---
id: mi-card-stack-fan
type: effect
title: "Fanning stack"
summary: "A stack of sheets behind a card that fan out when the card is hovered."
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
preview: assets/preview/mi-card-stack-fan.jpg
---

## Fanning stack

A stack of sheets behind a card that fan out when the card is hovered. The stack hints at more behind it: albums, collections, versions.

Markup:

```html
<article class="mi-card-stack-fan"><i></i><i></i><h3>Photo set</h3><p>24 pictures</p></article>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
