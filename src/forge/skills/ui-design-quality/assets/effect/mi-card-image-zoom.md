---
id: mi-card-image-zoom
type: effect
title: "Image zoom"
summary: "A card whose picture zooms slowly inside its frame on hover."
moods: [clear, modern]
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
preview: assets/preview/mi-card-image-zoom.jpg
---

## Image zoom

A card whose picture zooms slowly inside its frame on hover. Give the picture overflow:hidden on its frame, as here, or the zoom spills over the card edge.

Markup:

```html
<article class="mi-card-image-zoom"><svg viewBox="0 0 200 140" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><rect width="200" height="140" fill="#6366f1"/><circle cx="150" cy="40" r="26" fill="#fde68a"/><path d="M0 110c40-30 80-20 120 0s60 10 80-10v50H0z" fill="#4338ca"/></svg><p>Autumn programme</p></article>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
