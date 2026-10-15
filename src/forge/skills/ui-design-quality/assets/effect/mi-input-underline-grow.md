---
id: mi-input-underline-grow
type: effect
title: "Growing underline"
summary: "A minimal field whose underline grows from the centre when focused."
moods: [editorial, calm]
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
---

## Growing underline

A minimal field whose underline grows from the centre when focused. The wrapper draws the line, so the input's own outline is removed: keep the growing line visible enough (2 px).

Markup:

```html
<div class="mi-input-underline-grow"><input aria-label="Name" placeholder="Your name"></div>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
