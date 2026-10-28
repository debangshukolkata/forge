---
id: mi-btn-ripple
type: effect
title: "Press ripple"
summary: "A light ripple grows from the centre while the button is pressed."
moods: [clear, modern]
products: [apps, forms, marketing]
tags: [animation, motion, micro-interaction, button, css, no build step]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (micro-interaction kit, D-382)"
tested: "demo page in Edge: the action (hover, focus, check, press or invalid) changes the probed property or the animation runs, and it is switched off under reduced motion (tests/test_micro_effects.py, D-382)"
files:
  - from: recipes/motion-micro.css
    to: src/motion-micro.css
preview: assets/preview/mi-btn-ripple.jpg
---

## Press ripple

A light ripple grows from the centre while the button is pressed. Pure CSS and centred; a ripple from the pointer position needs a little JavaScript.

Markup:

```html
<button class="mi-btn-ripple">Send</button>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
