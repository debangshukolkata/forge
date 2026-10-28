---
id: mi-input-invalid-shake
type: effect
title: "Invalid shake"
summary: "A field that shakes once and shows a red border when its value is invalid after the person leaves it."
moods: [clear, robust]
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
preview: assets/preview/mi-input-invalid-shake.jpg
---

## Invalid shake

A field that shakes once and shows a red border when its value is invalid after the person leaves it. Uses :user-invalid, so nothing happens before the person has typed; always show the error text as well, never motion alone.

Markup:

```html
<input class="mi-input-invalid-shake" type="email" required aria-label="Email" placeholder="you@example.com">
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
