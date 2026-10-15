---
id: mi-toggle-slide
type: effect
title: "Sliding switch"
summary: "A switch whose knob slides and whose track changes colour."
moods: [clear, modern]
products: [apps, forms, marketing]
tags: [animation, motion, micro-interaction, toggle, css, no build step]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (micro-interaction kit, D-382)"
tested: "demo page in Edge: the action (hover, focus, check, press or invalid) changes the probed property or the animation runs, and it is switched off under reduced motion (tests/test_micro_effects.py, D-382)"
files:
  - from: recipes/motion-micro.css
    to: src/motion-micro.css
---

## Sliding switch

A switch whose knob slides and whose track changes colour. A real checkbox underneath: keyboard and screen readers work; label it with aria-label or a visible label.

Markup:

```html
<label class="mi-toggle-slide"><input type="checkbox" aria-label="Notifications"><span></span><i></i></label>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
