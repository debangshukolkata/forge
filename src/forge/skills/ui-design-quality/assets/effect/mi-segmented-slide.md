---
id: mi-segmented-slide
type: effect
title: "Sliding segmented control"
summary: "A segmented control whose highlight slides to the chosen option."
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
preview: assets/preview/mi-segmented-slide.jpg
---

## Sliding segmented control

A segmented control whose highlight slides to the chosen option. Exactly three options as written; for another count change the width and the translate steps.

Markup:

```html
<div class="mi-segmented-slide" role="radiogroup" aria-label="View"><input type="radio" name="seg" id="seg1" checked><label for="seg1">Day</label><input type="radio" name="seg" id="seg2"><label for="seg2">Week</label><input type="radio" name="seg" id="seg3"><label for="seg3">Month</label><i></i></div>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
