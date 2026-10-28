---
id: fx-check-draw
type: effect
title: Success check draw
summary: A check mark draws itself.
moods: [friendly, clear]
products: [forms, confirmations, checkout]
tags: [animation, motion, feedback]
density: any
dependencies: []
licence: original
source: authored for DebCraft (motion kit part 2, D-269)
tested: "demo page in Edge: the class animates or transitions as described, no console errors, switched off under reduced motion (tests/test_motion_more.py, D-269)"
files:
  - from: recipes/motion-more.css
    to: src/motion-more.css
preview: assets/preview/fx-check-draw.jpg
---

## Success check draw

`<svg class="check-draw" ... stroke="currentColor"><path d="M4 12l5 5L20 6"/></svg>`; set stroke and fill none on the svg.

Import the stylesheet once in main.tsx after index.css: `import "./motion-more.css"`. Budget: count it against the MOTION_INTENSITY dial (hover and focus effects are free); everything stops under `prefers-reduced-motion`.
