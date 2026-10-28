---
id: mi-card-border-gradient
type: effect
title: "Moving gradient border"
summary: "A two-colour gradient border that slides around the card on hover."
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
preview: assets/preview/mi-card-border-gradient.jpg
---

## Moving gradient border

A two-colour gradient border that slides around the card on hover. Mark one card as featured; the effect loses meaning if every card has it.

Markup:

```html
<article class="mi-card-border-gradient"><h3>Featured plan</h3><p>Most people choose this.</p></article>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
