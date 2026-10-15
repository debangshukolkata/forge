---
id: mi-btn-icon-spin
type: effect
title: "Icon turn"
summary: "The icon in a button turns a quarter on hover."
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
---

## Icon turn

The icon in a button turns a quarter on hover. A plus that turns into a cross suggests adding; keep the label.

Markup:

```html
<button class="mi-btn-icon-spin"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>Add member</button>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
