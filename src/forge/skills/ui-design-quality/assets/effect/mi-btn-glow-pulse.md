---
id: mi-btn-glow-pulse
type: effect
title: "Glow pulse"
summary: "A slow pulse of light around a call to action that needs attention."
moods: [urgent, warm]
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
preview: assets/preview/mi-btn-glow-pulse.jpg
---

## Glow pulse

A slow pulse of light around a call to action that needs attention. One per page at most; it stops under prefers-reduced-motion.

Markup:

```html
<button class="mi-btn-glow-pulse">Give blood today</button>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
