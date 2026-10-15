---
id: mi-input-glow
type: effect
title: "Glow focus"
summary: "A coloured glow and a stronger border on focus: for dark interfaces."
moods: [technical, dark]
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

## Glow focus

A coloured glow and a stronger border on focus: for dark interfaces. Best on dark surfaces; on light ones prefer mi-input-ring.

Markup:

```html
<input class="mi-input-glow" aria-label="Command" placeholder="Type a command">
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
