---
id: mi-input-float-label
type: effect
title: "Floating label"
summary: "A label that sits in the field and floats above it when the field is focused or filled."
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
---

## Floating label

A label that sits in the field and floats above it when the field is focused or filled. Keep placeholder=" " on the input: the CSS reads :placeholder-shown.

Markup:

```html
<div class="mi-input-float-label"><input id="mi-f1" placeholder=" "><label for="mi-f1">Email address</label></div>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
