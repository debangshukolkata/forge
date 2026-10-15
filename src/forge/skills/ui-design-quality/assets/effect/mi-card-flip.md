---
id: mi-card-flip
type: effect
title: "Flip card"
summary: "A card that turns over to show its back on hover or focus."
moods: [playful, friendly]
products: [apps, forms, marketing]
tags: [animation, motion, micro-interaction, card, css, no build step]
density: any
dependencies: []
licence: original
source: "authored for DebCraft (micro-interaction kit, D-382)"
tested: "demo page in Edge: the action (hover, focus, check, press or invalid) changes the probed property or the animation runs, and it is switched off under reduced motion (tests/test_micro_effects.py, D-382)"
files:
  - from: recipes/motion-micro.css
    to: src/motion-micro.css
---

## Flip card

A card that turns over to show its back on hover or focus. Only for short, optional content on the back; do not hide what people need.

Markup:

```html
<article class="mi-card-flip" tabindex="0"><div class="in"><div class="f"><h3>Who can give?</h3></div><div class="b"><p>Anyone aged 17 to 65 in good health.</p></div></div></article>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
