---
id: mi-radio-pop
type: effect
title: "Popping radio"
summary: "A radio whose centre dot pops in with a small overshoot."
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
preview: assets/preview/mi-radio-pop.jpg
---

## Popping radio

A radio whose centre dot pops in with a small overshoot. Group radios with the same name; the dot is the ::after of the span.

Markup:

```html
<label class="mi-radio-pop"><input type="radio" name="plan" value="a"><span></span>Monthly</label>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
