---
id: mi-input-search-expand
type: effect
title: "Expanding search"
summary: "A search field that is an icon button until focused, then opens wide."
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
preview: assets/preview/mi-input-search-expand.jpg
---

## Expanding search

A search field that is an icon button until focused, then opens wide. Collapsed it is a 44 px target; on a phone let it open to the full width of the header.

Markup:

```html
<div class="mi-input-search-expand"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6"/><path d="m16 16 4 4"/></svg><input type="search" aria-label="Search"></div>
```

Import the stylesheet once, after index.css: `import "./motion-micro.css"` (it holds all forty micro-interactions; keep the classes you use). It reads the project's tokens with fallbacks and stops under `prefers-reduced-motion`; do not rely on motion alone to say something (show a text state too).
